"""Tests for material inventory tracking."""

import pytest
import json
from pathlib import Path

from src.materials.inventory import (
    Spool,
    LowStockAlert,
    InventoryManager,
)


class TestSpool:
    """Tests for Spool dataclass."""

    def test_create_spool(self):
        """Test creating a spool."""
        spool = Spool(
            id="abc123",
            material="pla",
            brand="Hatchbox",
            color="Red",
            weight_grams=1000,
            remaining_grams=750,
            cost_per_kg=25.0,
        )

        assert spool.id == "abc123"
        assert spool.material == "pla"
        assert spool.brand == "Hatchbox"
        assert spool.remaining_grams == 750

    def test_remaining_percent(self):
        """Test remaining percentage calculation."""
        spool = Spool(
            id="test",
            material="pla",
            brand="Test",
            color="Blue",
            weight_grams=1000,
            remaining_grams=250,
            cost_per_kg=20.0,
        )

        assert spool.remaining_percent == 25.0

    def test_remaining_percent_empty(self):
        """Test remaining percentage when empty."""
        spool = Spool(
            id="test",
            material="pla",
            brand="Test",
            color="Blue",
            weight_grams=0,
            remaining_grams=0,
            cost_per_kg=20.0,
        )

        assert spool.remaining_percent == 0

    def test_remaining_meters(self):
        """Test remaining meters calculation."""
        spool = Spool(
            id="test",
            material="pla",
            brand="Test",
            color="Blue",
            weight_grams=1000,
            remaining_grams=500,
            cost_per_kg=20.0,
        )

        # Should return a positive value
        assert spool.remaining_meters > 0

    def test_remaining_cost(self):
        """Test remaining cost calculation."""
        spool = Spool(
            id="test",
            material="pla",
            brand="Test",
            color="Blue",
            weight_grams=1000,
            remaining_grams=500,
            cost_per_kg=20.0,
        )

        # 500g at $20/kg = $10
        assert spool.remaining_cost == 10.0

    def test_use_material(self):
        """Test using material from spool."""
        spool = Spool(
            id="test",
            material="pla",
            brand="Test",
            color="Blue",
            weight_grams=1000,
            remaining_grams=500,
            cost_per_kg=20.0,
        )

        result = spool.use(100)
        assert result is True
        assert spool.remaining_grams == 400
        assert spool.last_used is not None

    def test_use_material_insufficient(self):
        """Test using more material than available."""
        spool = Spool(
            id="test",
            material="pla",
            brand="Test",
            color="Blue",
            weight_grams=1000,
            remaining_grams=50,
            cost_per_kg=20.0,
        )

        result = spool.use(100)
        assert result is False
        assert spool.remaining_grams == 50

    def test_spool_to_dict(self):
        """Test spool serialization."""
        spool = Spool(
            id="test",
            material="petg",
            brand="Brand",
            color="Black",
            weight_grams=1000,
            remaining_grams=800,
            cost_per_kg=30.0,
        )

        d = spool.to_dict()
        assert d["id"] == "test"
        assert d["material"] == "petg"
        assert d["remaining_grams"] == 800

    def test_spool_from_dict(self):
        """Test spool deserialization."""
        data = {
            "id": "xyz",
            "material": "abs",
            "brand": "TestBrand",
            "color": "White",
            "weight_grams": 1000,
            "remaining_grams": 600,
            "cost_per_kg": 25.0,
            "diameter": 1.75,
        }

        spool = Spool.from_dict(data)
        assert spool.id == "xyz"
        assert spool.material == "abs"
        assert spool.remaining_grams == 600


class TestInventoryManager:
    """Tests for InventoryManager class."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create an inventory manager with temp file."""
        data_file = tmp_path / "inventory.json"
        return InventoryManager(data_file=data_file)

    def test_add_spool(self, manager):
        """Test adding a spool."""
        spool = manager.add_spool(
            material="PLA",
            brand="Hatchbox",
            color="Red",
            weight_grams=1000,
            cost_per_kg=25.0,
        )

        assert spool.id is not None
        assert spool.material == "pla"
        assert spool.brand == "Hatchbox"
        assert len(manager.spools) == 1

    def test_remove_spool(self, manager):
        """Test removing a spool."""
        spool = manager.add_spool(
            material="PLA",
            brand="Test",
            color="Blue",
        )

        result = manager.remove_spool(spool.id)
        assert result is True
        assert len(manager.spools) == 0

    def test_remove_nonexistent_spool(self, manager):
        """Test removing nonexistent spool."""
        result = manager.remove_spool("nonexistent")
        assert result is False

    def test_get_spool(self, manager):
        """Test getting a spool by ID."""
        spool = manager.add_spool(
            material="PETG",
            brand="Test",
            color="Green",
        )

        retrieved = manager.get_spool(spool.id)
        assert retrieved is not None
        assert retrieved.id == spool.id

    def test_get_nonexistent_spool(self, manager):
        """Test getting nonexistent spool."""
        result = manager.get_spool("nonexistent")
        assert result is None

    def test_get_spools_by_material(self, manager):
        """Test getting spools by material."""
        manager.add_spool(material="PLA", brand="A", color="Red")
        manager.add_spool(material="PLA", brand="B", color="Blue")
        manager.add_spool(material="PETG", brand="C", color="Green")

        pla_spools = manager.get_spools_by_material("PLA")
        assert len(pla_spools) == 2

    def test_get_spools_by_color(self, manager):
        """Test getting spools by color."""
        manager.add_spool(material="PLA", brand="A", color="Red")
        manager.add_spool(material="PETG", brand="B", color="Red")
        manager.add_spool(material="ABS", brand="C", color="Blue")

        red_spools = manager.get_spools_by_color("Red")
        assert len(red_spools) == 2

    def test_use_material(self, manager):
        """Test using material from inventory."""
        spool = manager.add_spool(
            material="PLA",
            brand="Test",
            color="Blue",
            weight_grams=1000,
        )

        result = manager.use_material(spool.id, 100)
        assert result is True

        retrieved = manager.get_spool(spool.id)
        assert retrieved.remaining_grams == 900

    def test_use_material_insufficient(self, manager):
        """Test using more material than available."""
        spool = manager.add_spool(
            material="PLA",
            brand="Test",
            color="Blue",
            weight_grams=100,
        )

        result = manager.use_material(spool.id, 200)
        assert result is False

    def test_use_material_nonexistent_spool(self, manager):
        """Test using material from nonexistent spool."""
        result = manager.use_material("nonexistent", 100)
        assert result is False

    def test_estimate_usage(self, manager):
        """Test finding spools for a print job."""
        manager.add_spool(material="PLA", brand="A", color="Red", weight_grams=1000)
        manager.add_spool(material="PLA", brand="B", color="Blue", weight_grams=500)
        manager.add_spool(material="PETG", brand="C", color="Green", weight_grams=1000)

        # Need 300g of PLA
        suitable = manager.estimate_usage(300, "PLA")
        assert len(suitable) == 2

        # Need 600g of PLA (only one spool has enough)
        suitable = manager.estimate_usage(600, "PLA")
        assert len(suitable) == 1

    def test_get_low_stock_alerts(self, manager):
        """Test getting low stock alerts."""
        # Add a full spool
        manager.add_spool(material="PLA", brand="Full", color="Red", weight_grams=1000)

        # Add a low spool
        spool = manager.add_spool(material="PLA", brand="Low", color="Blue", weight_grams=1000)
        spool.remaining_grams = 100  # 10% remaining
        manager._save()

        alerts = manager.get_low_stock_alerts()
        assert len(alerts) == 1
        assert alerts[0].spool_id == spool.id

    def test_get_total_inventory_value(self, manager):
        """Test getting total inventory value."""
        manager.add_spool(
            material="PLA", brand="A", color="Red",
            weight_grams=1000, cost_per_kg=20.0
        )
        manager.add_spool(
            material="PETG", brand="B", color="Blue",
            weight_grams=1000, cost_per_kg=30.0
        )

        # Two full spools: $20 + $30 = $50
        total = manager.get_total_inventory_value()
        assert total == 50.0

    def test_get_inventory_summary_empty(self, manager):
        """Test inventory summary with empty inventory."""
        summary = manager.get_inventory_summary()

        assert summary["total_spools"] == 0
        assert summary["total_weight_grams"] == 0
        assert summary["total_value"] == 0

    def test_get_inventory_summary(self, manager):
        """Test inventory summary."""
        manager.add_spool(material="PLA", brand="A", color="Red", weight_grams=1000)
        manager.add_spool(material="PLA", brand="B", color="Blue", weight_grams=500)
        manager.add_spool(material="PETG", brand="C", color="Green", weight_grams=1000)

        summary = manager.get_inventory_summary()

        assert summary["total_spools"] == 3
        assert summary["total_weight_grams"] == 2500
        assert "pla" in summary["materials"]
        assert summary["materials"]["pla"]["spool_count"] == 2

    def test_list_all(self, manager):
        """Test listing all spools."""
        manager.add_spool(material="PLA", brand="A", color="Red")
        manager.add_spool(material="PETG", brand="B", color="Blue")

        all_spools = manager.list_all()
        assert len(all_spools) == 2

    def test_persistence(self, tmp_path):
        """Test inventory persistence across instances."""
        data_file = tmp_path / "persist.json"

        # Create first manager and add spools
        manager1 = InventoryManager(data_file=data_file)
        manager1.add_spool(material="PLA", brand="Test", color="Red")
        manager1.add_spool(material="PETG", brand="Test", color="Blue")

        # Create second manager with same file
        manager2 = InventoryManager(data_file=data_file)

        assert len(manager2.spools) == 2


class TestLowStockAlert:
    """Tests for LowStockAlert dataclass."""

    def test_create_alert(self):
        """Test creating an alert."""
        alert = LowStockAlert(
            spool_id="abc123",
            material="pla",
            brand="Hatchbox",
            color="Red",
            remaining_percent=15.0,
            remaining_grams=150,
            message="Low stock alert",
        )

        assert alert.spool_id == "abc123"
        assert alert.remaining_percent == 15.0


class TestIntegration:
    """Integration tests for inventory system."""

    def test_print_workflow(self, tmp_path):
        """Test complete print workflow with inventory."""
        data_file = tmp_path / "workflow.json"
        manager = InventoryManager(data_file=data_file)

        # Add spools
        spool = manager.add_spool(
            material="PLA",
            brand="Hatchbox",
            color="Red",
            weight_grams=1000,
            cost_per_kg=25.0,
        )

        # Check if spool can fulfill print
        suitable = manager.estimate_usage(50, "PLA")
        assert len(suitable) == 1

        # Use material for print
        result = manager.use_material(spool.id, 50)
        assert result is True

        # Check remaining
        updated = manager.get_spool(spool.id)
        assert updated.remaining_grams == 950

        # Check value
        summary = manager.get_inventory_summary()
        assert summary["total_weight_grams"] == 950

    def test_multiple_prints_low_stock(self, tmp_path):
        """Test multiple prints leading to low stock."""
        data_file = tmp_path / "lowstock.json"
        manager = InventoryManager(data_file=data_file)
        manager.low_stock_threshold = 30.0

        # Add spool with 300g
        spool = manager.add_spool(
            material="PLA",
            brand="Test",
            color="Blue",
            weight_grams=300,
        )

        # No alerts initially (100%)
        alerts = manager.get_low_stock_alerts()
        assert len(alerts) == 0

        # Use 200g (33% remaining)
        manager.use_material(spool.id, 200)

        # Still no alert (above 30%)
        alerts = manager.get_low_stock_alerts()
        assert len(alerts) == 0

        # Use 20g more (27% remaining)
        manager.use_material(spool.id, 20)

        # Now should have alert
        alerts = manager.get_low_stock_alerts()
        assert len(alerts) == 1
