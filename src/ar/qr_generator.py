"""QR code generator for AR preview URLs.

Generates QR codes that link to AR preview pages.
When scanned on iOS, these open the model in AR Quick Look.
"""

import base64
import io
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("ar.qr_generator")


class ErrorCorrection(str, Enum):
    """QR code error correction levels."""
    LOW = "L"  # 7% recovery
    MEDIUM = "M"  # 15% recovery
    QUARTILE = "Q"  # 25% recovery
    HIGH = "H"  # 30% recovery


@dataclass
class QRConfig:
    """Configuration for QR code generation."""
    size: int = 256  # Image size in pixels
    border: int = 4  # Border size in modules
    error_correction: ErrorCorrection = ErrorCorrection.MEDIUM
    fill_color: str = "black"
    back_color: str = "white"
    logo_path: Optional[str] = None  # Optional logo to embed


class QRGenerator:
    """
    Generates QR codes for AR preview URLs.

    The QR codes can be scanned with an iPhone camera to open
    the AR preview directly in AR Quick Look.
    """

    def __init__(self, config: Optional[QRConfig] = None):
        """
        Initialize QR generator.

        Args:
            config: QR code configuration
        """
        self.config = config or QRConfig()
        settings = get_settings()
        self._output_dir = Path(settings.output_dir) / "ar" / "qr"
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def _check_qrcode_available(self) -> bool:
        """Check if qrcode library is available."""
        try:
            import qrcode
            return True
        except ImportError:
            return False

    def generate(
        self,
        url: str,
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate a QR code for a URL.

        Args:
            url: URL to encode
            output_path: Optional output path for the image

        Returns:
            Path to generated QR code image or None if failed
        """
        if not self._check_qrcode_available():
            logger.warning("qrcode library not installed, using fallback")
            return self._generate_fallback(url, output_path)

        try:
            import qrcode
            from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H

            # Map error correction
            ec_map = {
                ErrorCorrection.LOW: ERROR_CORRECT_L,
                ErrorCorrection.MEDIUM: ERROR_CORRECT_M,
                ErrorCorrection.QUARTILE: ERROR_CORRECT_Q,
                ErrorCorrection.HIGH: ERROR_CORRECT_H,
            }

            qr = qrcode.QRCode(
                version=1,
                error_correction=ec_map[self.config.error_correction],
                box_size=10,
                border=self.config.border,
            )
            qr.add_data(url)
            qr.make(fit=True)

            img = qr.make_image(
                fill_color=self.config.fill_color,
                back_color=self.config.back_color,
            )

            # Resize to target size
            img = img.resize((self.config.size, self.config.size))

            # Add logo if configured
            if self.config.logo_path:
                img = self._add_logo(img)

            # Determine output path
            if output_path:
                out_file = Path(output_path)
            else:
                qr_id = str(uuid4())[:8]
                out_file = self._output_dir / f"qr_{qr_id}.png"

            img.save(str(out_file))
            logger.info(f"QR code generated: {out_file}")

            return str(out_file)

        except Exception as e:
            logger.error(f"QR generation failed: {e}")
            return None

    def generate_base64(self, url: str) -> Optional[str]:
        """
        Generate a QR code and return as base64 data URL.

        Args:
            url: URL to encode

        Returns:
            Base64 data URL string or None if failed
        """
        if not self._check_qrcode_available():
            return self._generate_fallback_base64(url)

        try:
            import qrcode
            from qrcode.constants import ERROR_CORRECT_M

            qr = qrcode.QRCode(
                version=1,
                error_correction=ERROR_CORRECT_M,
                box_size=10,
                border=self.config.border,
            )
            qr.add_data(url)
            qr.make(fit=True)

            img = qr.make_image(
                fill_color=self.config.fill_color,
                back_color=self.config.back_color,
            )
            img = img.resize((self.config.size, self.config.size))

            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            b64 = base64.b64encode(buffer.getvalue()).decode()

            return f"data:image/png;base64,{b64}"

        except Exception as e:
            logger.error(f"QR base64 generation failed: {e}")
            return None

    def _add_logo(self, qr_img):
        """Add a logo to the center of the QR code."""
        try:
            from PIL import Image

            logo = Image.open(self.config.logo_path)

            # Logo should be about 20% of QR size
            logo_size = self.config.size // 5
            logo = logo.resize((logo_size, logo_size))

            # Calculate position
            pos = ((self.config.size - logo_size) // 2, (self.config.size - logo_size) // 2)

            # Paste logo
            qr_img = qr_img.convert("RGBA")
            logo = logo.convert("RGBA")
            qr_img.paste(logo, pos, logo)

            return qr_img

        except Exception as e:
            logger.warning(f"Failed to add logo: {e}")
            return qr_img

    def _generate_fallback(self, url: str, output_path: Optional[str]) -> Optional[str]:
        """Generate a placeholder image when qrcode library is not available."""
        try:
            # Create a simple placeholder image
            from PIL import Image, ImageDraw, ImageFont

            img = Image.new("RGB", (self.config.size, self.config.size), self.config.back_color)
            draw = ImageDraw.Draw(img)

            # Draw border
            draw.rectangle(
                [0, 0, self.config.size - 1, self.config.size - 1],
                outline=self.config.fill_color,
                width=2,
            )

            # Draw text placeholder
            text = "QR Code\n(Install qrcode)"
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None

            # Center text
            bbox = draw.textbbox((0, 0), text, font=font) if font else (0, 0, 100, 30)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (self.config.size - text_width) // 2
            y = (self.config.size - text_height) // 2
            draw.text((x, y), text, fill=self.config.fill_color, font=font)

            # Determine output path
            if output_path:
                out_file = Path(output_path)
            else:
                qr_id = str(uuid4())[:8]
                out_file = self._output_dir / f"qr_placeholder_{qr_id}.png"

            img.save(str(out_file))
            return str(out_file)

        except ImportError:
            logger.error("PIL not available for fallback QR generation")
            return None
        except Exception as e:
            logger.error(f"Fallback QR generation failed: {e}")
            return None

    def _generate_fallback_base64(self, url: str) -> Optional[str]:
        """Generate a placeholder base64 image."""
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (self.config.size, self.config.size), self.config.back_color)
            draw = ImageDraw.Draw(img)
            draw.rectangle(
                [0, 0, self.config.size - 1, self.config.size - 1],
                outline=self.config.fill_color,
                width=2,
            )
            draw.text((10, 10), "QR Placeholder", fill=self.config.fill_color)

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            b64 = base64.b64encode(buffer.getvalue()).decode()

            return f"data:image/png;base64,{b64}"

        except Exception as e:
            logger.error(f"Fallback base64 generation failed: {e}")
            return None


def generate_qr_code(
    url: str,
    output_path: Optional[str] = None,
    size: int = 256,
) -> Optional[str]:
    """
    Convenience function to generate a QR code.

    Args:
        url: URL to encode
        output_path: Optional output path
        size: Image size in pixels

    Returns:
        Path to generated QR code or None if failed
    """
    config = QRConfig(size=size)
    generator = QRGenerator(config)
    return generator.generate(url, output_path)
