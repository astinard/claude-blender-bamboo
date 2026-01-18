"""Tests for batch nesting module."""

import pytest
from pathlib import Path

from src.nesting.batch_nester import (
    BatchNester,
    NestingConfig,
    NestingResult,
    PlacedPart,
    NestingStrategy,
    create_nester,
    nest_parts,
)


class TestNestingStrategy:
    """Tests for NestingStrategy enum."""

    def test_strategy_values(self):
        """Test strategy values."""
        assert NestingStrategy.DENSITY.value == "density"
        assert NestingStrategy.HEIGHT.value == "height"
        assert NestingStrategy.SPACING.value == "spacing"
        assert NestingStrategy.SEQUENTIAL.value == "sequential"


class TestPlacedPart:
    """Tests for PlacedPart dataclass."""

    def test_create_part(self):
        """Test creating a placed part."""
        part = PlacedPart(
            name="test_part",
            file_path="/path/to/part.stl",
            x=10.0,
            y=20.0,
            rotation=90.0,
            width=50.0,
            depth=30.0,
            height=25.0,
        )

        assert part.name == "test_part"
        assert part.x == 10.0
        assert part.y == 20.0
        assert part.rotation == 90.0

    def test_to_dict(self):
        """Test part serialization."""
        part = PlacedPart("test", "/path", 0, 0, 0, 10, 10, 10)
        d = part.to_dict()

        assert d["name"] == "test"
        assert "x" in d
        assert "y" in d


class TestNestingConfig:
    """Tests for NestingConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = NestingConfig()

        assert config.plate_width == 256.0
        assert config.plate_depth == 256.0
        assert config.part_spacing == 5.0
        assert config.edge_margin == 10.0
        assert config.strategy == NestingStrategy.DENSITY
        assert config.allow_rotation is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = NestingConfig(
            plate_width=200.0,
            plate_depth=200.0,
            part_spacing=10.0,
            strategy=NestingStrategy.HEIGHT,
        )

        assert config.plate_width == 200.0
        assert config.part_spacing == 10.0
        assert config.strategy == NestingStrategy.HEIGHT

    def test_to_dict(self):
        """Test config serialization."""
        config = NestingConfig(strategy=NestingStrategy.SPACING)
        d = config.to_dict()

        assert d["plate_width"] == 256.0
        assert d["strategy"] == "spacing"

    def test_from_dict(self):
        """Test config deserialization."""
        data = {
            "plate_width": 180.0,
            "plate_depth": 180.0,
            "strategy": "height",
        }
        config = NestingConfig.from_dict(data)

        assert config.plate_width == 180.0
        assert config.strategy == NestingStrategy.HEIGHT

    def test_for_printer(self):
        """Test printer-specific config."""
        config = NestingConfig.for_printer("bambu_x1c")

        assert config.plate_width == 256.0
        assert config.plate_depth == 256.0


class TestNestingResult:
    """Tests for NestingResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        parts = [PlacedPart("p1", "/p1", 0, 0, 0, 10, 10, 10)]
        result = NestingResult(
            success=True,
            placed_parts=parts,
            plate_utilization=25.0,
            total_height=10.0,
        )

        assert result.success is True
        assert len(result.placed_parts) == 1
        assert result.plate_utilization == 25.0

    def test_failure_result(self):
        """Test failure result."""
        result = NestingResult(
            success=False,
            error_message="No parts provided",
        )

        assert result.success is False
        assert result.error_message == "No parts provided"

    def test_to_dict(self):
        """Test result serialization."""
        result = NestingResult(
            success=True,
            placed_parts=[PlacedPart("p", "/p", 0, 0, 0, 10, 10, 10)],
            plate_utilization=50.0,
        )
        d = result.to_dict()

        assert d["success"] is True
        assert len(d["placed_parts"]) == 1


class TestBatchNester:
    """Tests for BatchNester class."""

    @pytest.fixture
    def nester(self):
        """Create a batch nester."""
        return BatchNester()

    @pytest.fixture
    def test_parts(self, tmp_path):
        """Create test part files."""
        parts = []
        for i in range(3):
            part_path = tmp_path / f"part_{i}.obj"
            part_path.write_text(f"""# Part {i}
v 0 0 0
v {20 + i * 5} 0 0
v {20 + i * 5} {20 + i * 5} 0
v 0 {20 + i * 5} 0
v 0 0 {10 + i * 5}
f 1 2 3 4
f 1 5 2
""")
            parts.append(str(part_path))
        return parts

    def test_init(self, nester):
        """Test nester initialization."""
        assert nester.config is not None
        assert nester.config.plate_width == 256.0

    def test_init_custom_config(self):
        """Test nester with custom config."""
        config = NestingConfig(plate_width=200.0)
        nester = BatchNester(config=config)

        assert nester.config.plate_width == 200.0

    def test_nest_no_parts(self, nester):
        """Test nesting with no parts."""
        result = nester.nest_parts([])

        assert result.success is False
        assert "No parts" in result.error_message

    def test_nest_single_part(self, nester, test_parts):
        """Test nesting single part."""
        result = nester.nest_parts([test_parts[0]])

        assert result.success is True
        assert len(result.placed_parts) == 1
        assert len(result.unplaced_parts) == 0

    def test_nest_multiple_parts(self, nester, test_parts):
        """Test nesting multiple parts."""
        result = nester.nest_parts(test_parts)

        assert result.success is True
        assert len(result.placed_parts) > 0
        assert result.plate_utilization > 0

    def test_nest_nonexistent_parts(self, nester):
        """Test nesting with non-existent files."""
        result = nester.nest_parts(["/nonexistent/part.obj"])

        assert result.success is False

    def test_nest_result_has_positions(self, nester, test_parts):
        """Test that placed parts have positions."""
        result = nester.nest_parts(test_parts)

        assert result.success is True
        for part in result.placed_parts:
            assert part.x >= 0
            assert part.y >= 0
            assert part.width > 0
            assert part.depth > 0


class TestPartPlacement:
    """Tests for part placement algorithm."""

    @pytest.fixture
    def nester(self):
        """Create a batch nester."""
        return BatchNester()

    def test_can_place_empty(self, nester):
        """Test placing part in empty space."""
        can_place = nester._can_place(0, 0, 10, 10, [])
        assert can_place is True

    def test_can_place_no_overlap(self, nester):
        """Test placing part without overlap."""
        occupied = [(0, 0, 20, 20)]
        can_place = nester._can_place(25, 0, 10, 10, occupied)
        assert can_place is True

    def test_can_place_with_overlap(self, nester):
        """Test placing part with overlap."""
        occupied = [(0, 0, 20, 20)]
        can_place = nester._can_place(10, 10, 15, 15, occupied)
        assert can_place is False

    def test_find_position_empty(self, nester):
        """Test finding position in empty space."""
        pos = nester._find_position(10, 10, [], 100, 100)

        assert pos is not None
        assert pos[0] >= 0
        assert pos[1] >= 0

    def test_find_position_occupied(self, nester):
        """Test finding position with occupied space."""
        occupied = [(0, 0, 50, 50)]
        pos = nester._find_position(10, 10, occupied, 100, 100)

        assert pos is not None
        # Should be placed outside occupied area
        assert pos[0] >= 50 or pos[1] >= 50


class TestUtilization:
    """Tests for plate utilization calculation."""

    @pytest.fixture
    def nester(self):
        """Create a batch nester with known plate size."""
        config = NestingConfig(
            plate_width=100.0,
            plate_depth=100.0,
            edge_margin=0.0,
        )
        return BatchNester(config=config)

    def test_calculate_utilization_empty(self, nester):
        """Test utilization with no parts."""
        util = nester._calculate_utilization([])
        assert util == 0.0

    def test_calculate_utilization_single(self, nester):
        """Test utilization with single part."""
        parts = [PlacedPart("p", "/p", 0, 0, 0, 50, 50, 10)]
        util = nester._calculate_utilization(parts)

        # 50x50 = 2500, plate = 100x100 = 10000
        assert util == 25.0

    def test_calculate_utilization_multiple(self, nester):
        """Test utilization with multiple parts."""
        parts = [
            PlacedPart("p1", "/p1", 0, 0, 0, 50, 50, 10),
            PlacedPart("p2", "/p2", 50, 0, 0, 50, 50, 10),
        ]
        util = nester._calculate_utilization(parts)

        # 2 * 2500 = 5000, plate = 10000
        assert util == 50.0


class TestExportLayout:
    """Tests for layout export."""

    @pytest.fixture
    def nester(self):
        """Create a batch nester."""
        return BatchNester()

    @pytest.fixture
    def test_result(self):
        """Create a test result."""
        return NestingResult(
            success=True,
            placed_parts=[
                PlacedPart("part1", "/part1.stl", 10, 20, 0, 30, 40, 15),
                PlacedPart("part2", "/part2.stl", 50, 20, 90, 25, 35, 20),
            ],
            unplaced_parts=["/part3.stl"],
            plate_utilization=45.0,
        )

    def test_export_layout(self, nester, test_result):
        """Test exporting layout."""
        layout = nester.export_layout(test_result)

        assert "Build plate layout" in layout
        assert "Utilization: 45.0%" in layout
        assert "part1" in layout
        assert "part2" in layout
        assert "Unplaced" in layout


class TestSorting:
    """Tests for part sorting strategies."""

    @pytest.fixture
    def nester(self):
        """Create a batch nester."""
        return BatchNester()

    @pytest.fixture
    def test_parts_data(self):
        """Create test part data."""
        return [
            {"path": "/p1", "name": "p1", "width": 10, "depth": 10, "height": 5},
            {"path": "/p2", "name": "p2", "width": 30, "depth": 30, "height": 15},
            {"path": "/p3", "name": "p3", "width": 20, "depth": 20, "height": 10},
        ]

    def test_sort_density(self, test_parts_data):
        """Test density sorting."""
        nester = BatchNester(NestingConfig(strategy=NestingStrategy.DENSITY))
        sorted_parts = nester._sort_parts(test_parts_data)

        # Largest area first
        assert sorted_parts[0]["name"] == "p2"
        assert sorted_parts[1]["name"] == "p3"

    def test_sort_height(self, test_parts_data):
        """Test height sorting."""
        nester = BatchNester(NestingConfig(strategy=NestingStrategy.HEIGHT))
        sorted_parts = nester._sort_parts(test_parts_data)

        # Tallest first
        assert sorted_parts[0]["name"] == "p2"
        assert sorted_parts[0]["height"] == 15

    def test_sort_sequential(self, test_parts_data):
        """Test sequential (no) sorting."""
        nester = BatchNester(NestingConfig(strategy=NestingStrategy.SEQUENTIAL))
        sorted_parts = nester._sort_parts(test_parts_data)

        # Original order
        assert sorted_parts[0]["name"] == "p1"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_nester(self):
        """Test create_nester function."""
        nester = create_nester(
            plate_width=200.0,
            plate_depth=180.0,
            strategy="height",
        )

        assert nester.config.plate_width == 200.0
        assert nester.config.plate_depth == 180.0
        assert nester.config.strategy == NestingStrategy.HEIGHT

    def test_nest_parts_function(self, tmp_path):
        """Test nest_parts convenience function."""
        # Create test parts
        parts = []
        for i in range(2):
            part_path = tmp_path / f"part_{i}.obj"
            part_path.write_text(f"v 0 0 0\nv 20 0 0\nv 20 20 0\nv 0 0 10\nf 1 2 3")
            parts.append(str(part_path))

        result = nest_parts(parts, plate_size=200.0, strategy="density")

        assert result.success is True
        assert len(result.placed_parts) > 0


class TestIntegration:
    """Integration tests for batch nesting."""

    @pytest.fixture
    def test_parts(self, tmp_path):
        """Create test part files."""
        parts = []
        sizes = [(20, 20, 10), (30, 30, 15), (25, 25, 12), (15, 15, 8)]
        for i, (w, d, h) in enumerate(sizes):
            part_path = tmp_path / f"part_{i}.obj"
            part_path.write_text(f"""v 0 0 0
v {w} 0 0
v {w} {d} 0
v 0 {d} 0
v 0 0 {h}
f 1 2 3 4
""")
            parts.append(str(part_path))
        return parts

    def test_full_workflow(self, test_parts):
        """Test complete nesting workflow."""
        # Create nester
        nester = create_nester(
            plate_width=100.0,
            plate_depth=100.0,
            strategy="density",
        )

        # Nest parts
        result = nester.nest_parts(test_parts)
        assert result.success is True
        assert len(result.placed_parts) > 0

        # Verify positions are within plate
        for part in result.placed_parts:
            assert part.x >= 0
            assert part.y >= 0
            assert part.x + part.width <= 100
            assert part.y + part.depth <= 100

        # Export layout
        layout = nester.export_layout(result)
        assert len(layout) > 0

    def test_all_strategies(self, test_parts):
        """Test all nesting strategies."""
        for strategy in NestingStrategy:
            config = NestingConfig(strategy=strategy)
            nester = BatchNester(config=config)
            result = nester.nest_parts(test_parts)

            assert result.success is True, f"Strategy {strategy.value} failed"
            assert len(result.placed_parts) > 0
