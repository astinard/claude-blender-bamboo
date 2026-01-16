"""
File transfer module for Bamboo Labs printers.

Handles uploading print files to the printer via FTP/FTPS.
"""

import ftplib
import ssl
from pathlib import Path
from typing import Optional, List, Callable
from dataclasses import dataclass
import io


@dataclass
class TransferResult:
    """Result of a file transfer operation."""
    success: bool
    message: str
    remote_path: Optional[str] = None
    bytes_transferred: int = 0


@dataclass
class FileInfo:
    """Information about a file on the printer."""
    name: str
    size: int
    is_directory: bool
    path: str


class PrinterFileTransfer:
    """
    File transfer manager for Bamboo Labs printers.

    Uses FTPS (FTP over SSL) for secure file transfers.
    """

    FTP_PORT = 990
    FTP_USER = "bblp"

    def __init__(
        self,
        ip: str,
        access_code: str,
        use_mock: bool = False
    ):
        """
        Initialize file transfer.

        Args:
            ip: Printer IP address
            access_code: Printer access code (used as FTP password)
            use_mock: Use mock for testing
        """
        self.ip = ip
        self.access_code = access_code
        self.use_mock = use_mock

        self._ftp: Optional[ftplib.FTP_TLS] = None
        self._connected = False
        self._mock_files: List[FileInfo] = []

    def connect(self, timeout: float = 30.0) -> bool:
        """
        Connect to printer FTP server.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            True if connected successfully
        """
        if self.use_mock:
            self._connected = True
            return True

        try:
            # Create SSL context that doesn't verify certificates
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            self._ftp = ftplib.FTP_TLS(context=context)
            self._ftp.connect(self.ip, self.FTP_PORT, timeout=timeout)
            self._ftp.login(self.FTP_USER, self.access_code)
            self._ftp.prot_p()  # Enable data channel encryption

            self._connected = True
            return True

        except Exception as e:
            print(f"FTP connection error: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from FTP server."""
        if self._ftp:
            try:
                self._ftp.quit()
            except:
                pass
        self._ftp = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def upload_file(
        self,
        local_path: Path,
        remote_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> TransferResult:
        """
        Upload a file to the printer.

        Args:
            local_path: Path to local file
            remote_path: Remote path (default: /cache/{filename})
            progress_callback: Callback(bytes_sent, total_bytes)

        Returns:
            TransferResult with success status
        """
        local_path = Path(local_path)

        if not local_path.exists():
            return TransferResult(
                success=False,
                message=f"Local file not found: {local_path}"
            )

        if remote_path is None:
            remote_path = f"/cache/{local_path.name}"

        if self.use_mock:
            file_size = local_path.stat().st_size
            self._mock_files.append(FileInfo(
                name=local_path.name,
                size=file_size,
                is_directory=False,
                path=remote_path
            ))
            return TransferResult(
                success=True,
                message="Mock upload successful",
                remote_path=remote_path,
                bytes_transferred=file_size
            )

        if not self._connected or not self._ftp:
            return TransferResult(
                success=False,
                message="Not connected to printer"
            )

        try:
            file_size = local_path.stat().st_size
            bytes_sent = 0

            def upload_callback(data):
                nonlocal bytes_sent
                bytes_sent += len(data)
                if progress_callback:
                    progress_callback(bytes_sent, file_size)

            # Ensure directory exists
            dir_path = str(Path(remote_path).parent)
            try:
                self._ftp.mkd(dir_path)
            except ftplib.error_perm:
                pass  # Directory may already exist

            # Upload file
            with open(local_path, 'rb') as f:
                self._ftp.storbinary(
                    f'STOR {remote_path}',
                    f,
                    blocksize=8192,
                    callback=upload_callback
                )

            return TransferResult(
                success=True,
                message="Upload successful",
                remote_path=remote_path,
                bytes_transferred=bytes_sent
            )

        except Exception as e:
            return TransferResult(
                success=False,
                message=f"Upload failed: {str(e)}"
            )

    def download_file(
        self,
        remote_path: str,
        local_path: Path,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> TransferResult:
        """
        Download a file from the printer.

        Args:
            remote_path: Path on printer
            local_path: Local destination path
            progress_callback: Callback(bytes_received)

        Returns:
            TransferResult with success status
        """
        local_path = Path(local_path)

        if self.use_mock:
            return TransferResult(
                success=True,
                message="Mock download successful",
                remote_path=remote_path
            )

        if not self._connected or not self._ftp:
            return TransferResult(
                success=False,
                message="Not connected to printer"
            )

        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            bytes_received = 0

            def download_callback(data):
                nonlocal bytes_received
                bytes_received += len(data)
                if progress_callback:
                    progress_callback(bytes_received)

            with open(local_path, 'wb') as f:
                def write_callback(data):
                    f.write(data)
                    download_callback(data)

                self._ftp.retrbinary(
                    f'RETR {remote_path}',
                    write_callback,
                    blocksize=8192
                )

            return TransferResult(
                success=True,
                message="Download successful",
                remote_path=remote_path,
                bytes_transferred=bytes_received
            )

        except Exception as e:
            return TransferResult(
                success=False,
                message=f"Download failed: {str(e)}"
            )

    def list_files(self, path: str = "/") -> List[FileInfo]:
        """
        List files in a directory on the printer.

        Args:
            path: Directory path

        Returns:
            List of FileInfo objects
        """
        if self.use_mock:
            return [f for f in self._mock_files if f.path.startswith(path)]

        if not self._connected or not self._ftp:
            return []

        try:
            files = []
            self._ftp.cwd(path)

            # Get directory listing
            listing = []
            self._ftp.retrlines('LIST', listing.append)

            for line in listing:
                parts = line.split()
                if len(parts) >= 9:
                    name = " ".join(parts[8:])
                    size = int(parts[4]) if parts[4].isdigit() else 0
                    is_dir = line.startswith('d')
                    files.append(FileInfo(
                        name=name,
                        size=size,
                        is_directory=is_dir,
                        path=f"{path}/{name}".replace("//", "/")
                    ))

            return files

        except Exception as e:
            print(f"List files error: {e}")
            return []

    def delete_file(self, remote_path: str) -> TransferResult:
        """
        Delete a file from the printer.

        Args:
            remote_path: Path to file on printer

        Returns:
            TransferResult with success status
        """
        if self.use_mock:
            self._mock_files = [f for f in self._mock_files if f.path != remote_path]
            return TransferResult(
                success=True,
                message="Mock delete successful",
                remote_path=remote_path
            )

        if not self._connected or not self._ftp:
            return TransferResult(
                success=False,
                message="Not connected to printer"
            )

        try:
            self._ftp.delete(remote_path)
            return TransferResult(
                success=True,
                message="File deleted",
                remote_path=remote_path
            )
        except Exception as e:
            return TransferResult(
                success=False,
                message=f"Delete failed: {str(e)}"
            )

    def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists on the printer."""
        if self.use_mock:
            return any(f.path == remote_path for f in self._mock_files)

        if not self._connected or not self._ftp:
            return False

        try:
            self._ftp.size(remote_path)
            return True
        except:
            return False

    def get_free_space(self) -> Optional[int]:
        """
        Get free space on printer storage.

        Returns:
            Free space in bytes, or None if unavailable
        """
        if self.use_mock:
            return 1024 * 1024 * 1024  # 1 GB mock

        # Note: FTP doesn't have a standard way to get free space
        # Bambu printers may not support this
        return None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


class MockPrinterTransfer(PrinterFileTransfer):
    """Mock file transfer for testing without a printer."""

    def __init__(self):
        super().__init__(
            ip="127.0.0.1",
            access_code="mock",
            use_mock=True
        )
