"""Tests for material compatibility and inventory."""

import pytest
from pathlib import Path
import tempfile

from src.materials.material_db import (
    Material,
    MaterialType,
    MaterialProperties,
    get_material,
    get_materials_by_type,
    MATERIAL_DATABASE,
    list_all_materials,
)
from src.materials.compatibility import (
    CompatibilityLevel,
    CompatibilityResult,
    check_compatibility,
    check_multi_material_compatibility,
    get_ams_recommendations,
    suggest_support_material,
)
from src.materials.inventory import (
    Spool,
    InventoryManager,
)


class TestMaterialDatabase:
    """Tests for material database."""

    def test_get_material_exists(self):
        """Test getting an existing material."""
        mat = get_material("pla")
        assert mat is not None
        assert mat.name == "PLA"
        assert mat.material_type == MaterialType.PLA

    def test_get_material_case_insensitive(self):
        """Test case insensitive material lookup."""
        mat1 = get_material("PLA")
        mat2 = get_material("pla")
        mat3 = get_material("Pla")
        # All should work due to lowercase conversion
        assert mat1 is not None
        assert mat2 is not None
        assert mat3 is not None
        assert mat1.name == mat2.name == mat3.name

    def test_get_material_not_found(self):
        """Test getting a non-existent material."""
        mat = get_material("unobtainium")
        assert mat is None

    def test_get_materials_by_type(self):
        """Test filtering materials by type."""
        pla_materials = get_materials_by_type(MaterialType.PLA)
        assert len(pla_materials) >= 1
        assert all(m.material_type == MaterialType.PLA for m in pla_materials)

    def test_list_all_materials(self):
        """Test listing all materials."""
        all_mats = list_all_materials()
        assert len(all_mats) > 0
        assert "pla" in all_mats
        assert "petg" in all_mats
        assert "abs" in all_mats

    def test_material_properties(self):
        """Test material properties are correctly set."""
        pla = get_material("pla")
        assert pla.properties.nozzle_temp_min == 190
        assert pla.properties.nozzle_temp_max == 230
        assert pla.properties.requires_enclosure is False

        abs_mat = get_material("abs")
        assert abs_mat.properties.requires_enclosure is True
        assert abs_mat.properties.toxic_fumes is True


class TestCompatibility:
    """Tests for material compatibility checking."""

    def test_same_material_excellent(self):
        """Same material should have excellent compatibility."""
        result = check_compatibility("pla", "pla")
        assert result.level == CompatibilityLevel.EXCELLENT
        assert result.is_compatible

    def test_pla_petg_compatibility(self):
        """PLA and PETG have temperature differences."""
        result = check_compatibility("pla", "petg")
        # PLA bed temp (45-65) doesn't overlap PETG (70-90), so marked POOR
        assert result.level in [CompatibilityLevel.POOR, CompatibilityLevel.FAIR]
        assert len(result.issues) > 0  # Should have some temperature issues

    def test_pla_abs_incompatible(self):
        """PLA and ABS have poor adhesion."""
        result = check_compatibility("pla", "abs")
        assert result.level in [CompatibilityLevel.POOR, CompatibilityLevel.FAIR]

    def test_pla_pva_good(self):
        """PLA and PVA are designed to work together."""
        result = check_compatibility("pla", "pva")
        assert result.is_compatible

    def test_abs_hips_compatible(self):
        """ABS and HIPS work well together."""
        result = check_compatibility("abs", "hips")
        assert result.is_compatible

    def test_unknown_material(self):
        """Unknown material should return incompatible."""
        result = check_compatibility("pla", "unknown_material")
        assert result.level == CompatibilityLevel.INCOMPATIBLE
        assert not result.is_compatible

    def test_compatibility_result_str(self):
        """Test string representation of compatibility result."""
        result = check_compatibility("pla", "petg")
        text = str(result)
        assert "pla" in text.lower()
        assert "petg" in text.lower()

    def test_temperature_mismatch_warnings(self):
        """Materials with large temp differences should warn."""
        result = check_compatibility("pla", "pc")
        # PC requires much higher temp than PLA
        assert len(result.issues) > 0
        assert len(result.warnings) > 0

    def test_enclosure_requirement_warning(self):
        """Should warn when one material needs enclosure."""
        result = check_compatibility("pla", "abs")
        # ABS needs enclosure, PLA doesn't
        has_enclosure_warning = any("enclosure" in w.lower() for w in result.warnings)
        has_enclosure_issue = any("enclosure" in i.message.lower() for i in result.issues)
        assert has_enclosure_warning or has_enclosure_issue


class TestMultiMaterialCompatibility:
    """Tests for multi-material compatibility analysis."""

    def test_single_material(self):
        """Single material should be excellent."""
        result = check_multi_material_compatibility(["pla"])
        assert result.overall_compatibility == CompatibilityLevel.EXCELLENT

    def test_two_materials(self):
        """Two materials should produce pairwise results."""
        result = check_multi_material_compatibility(["pla", "petg"])
        assert len(result.pairwise_results) == 1
        assert result.materials == ["pla", "petg"]

    def test_three_materials(self):
        """Three materials should produce three pairwise results."""
        result = check_multi_material_compatibility(["pla", "petg", "pva"])
        assert len(result.pairwise_results) == 3
        assert len(result.ams_recommendations) == 3

    def test_print_settings_generated(self):
        """Should generate print settings recommendations."""
        result = check_multi_material_compatibility(["pla", "petg"])
        assert "nozzle_temp" in result.print_settings
        assert "bed_temp" in result.print_settings

    def test_ams_recommendations(self):
        """Should generate AMS slot recommendations."""
        result = check_multi_material_compatibility(["pla", "pva"])
        assert len(result.ams_recommendations) == 2
        # PVA should be last as support material
        assert result.ams_recommendations[-1].material == "pva"


class TestAMSRecommendations:
    """Tests for AMS slot recommendations."""

    def test_support_material_last(self):
        """Support materials should be recommended for last slots."""
        recs = get_ams_recommendations(["pla", "petg", "pva"])
        assert recs[-1].material == "pva"

    def test_main_materials_first(self):
        """Main materials should be in first slots."""
        recs = get_ams_recommendations(["pla", "pva"])
        assert recs[0].material == "pla"
        assert recs[1].material == "pva"

    def test_slot_numbers_sequential(self):
        """Slot numbers should be sequential starting from 1."""
        recs = get_ams_recommendations(["pla", "petg", "abs", "pva"])
        slots = [r.slot for r in recs]
        assert slots == [1, 2, 3, 4]


class TestSuggestSupportMaterial:
    """Tests for support material suggestions."""

    def test_pla_suggests_pva(self):
        """PLA should suggest PVA as support."""
        support = suggest_support_material("pla")
        assert support == "pva"

    def test_abs_suggests_hips(self):
        """ABS should suggest ABS or HIPS as support."""
        support = suggest_support_material("abs")
        # ABS compatible_supports is ["abs", "hips"], returns first non-PVA
        assert support in ["abs", "hips"]

    def test_unknown_material(self):
        """Unknown material should return None."""
        support = suggest_support_material("unknown")
        assert support is None


class TestInventory:
    """Tests for inventory management."""

    @pytest.fixture
    def temp_inventory(self, tmp_path):
        """Create a temporary inventory manager."""
        data_file = tmp_path / "test_inventory.json"
        return InventoryManager(data_file)

    def test_add_spool(self, temp_inventory):
        """Test adding a spool."""
        spool = temp_inventory.add_spool(
            material="pla",
            brand="Bambu",
            color="White",
            weight_grams=1000,
            cost_per_kg=25.0,
        )
        assert spool.id is not None
        assert spool.material == "pla"
        assert spool.remaining_grams == 1000
        assert spool.remaining_percent == 100.0

    def test_use_material(self, temp_inventory):
        """Test using material from a spool."""
        spool = temp_inventory.add_spool(
            material="pla",
            brand="Bambu",
            color="White",
            weight_grams=1000,
        )
        assert temp_inventory.use_material(spool.id, 100)
        updated = temp_inventory.get_spool(spool.id)
        assert updated.remaining_grams == 900

    def test_use_material_insufficient(self, temp_inventory):
        """Test using more material than available."""
        spool = temp_inventory.add_spool(
            material="pla",
            brand="Bambu",
            color="White",
            weight_grams=100,
        )
        assert not temp_inventory.use_material(spool.id, 200)

    def test_remove_spool(self, temp_inventory):
        """Test removing a spool."""
        spool = temp_inventory.add_spool(
            material="pla",
            brand="Bambu",
            color="White",
        )
        assert temp_inventory.remove_spool(spool.id)
        assert temp_inventory.get_spool(spool.id) is None

    def test_low_stock_alert(self, temp_inventory):
        """Test low stock alerts."""
        spool = temp_inventory.add_spool(
            material="pla",
            brand="Bambu",
            color="White",
            weight_grams=1000,
        )
        # Use 90% of material
        temp_inventory.use_material(spool.id, 900)
        alerts = temp_inventory.get_low_stock_alerts()
        assert len(alerts) == 1
        assert alerts[0].spool_id == spool.id

    def test_get_spools_by_material(self, temp_inventory):
        """Test filtering spools by material."""
        temp_inventory.add_spool(material="pla", brand="A", color="White")
        temp_inventory.add_spool(material="pla", brand="B", color="Black")
        temp_inventory.add_spool(material="petg", brand="C", color="Clear")

        pla_spools = temp_inventory.get_spools_by_material("pla")
        assert len(pla_spools) == 2

    def test_inventory_summary(self, temp_inventory):
        """Test inventory summary statistics."""
        temp_inventory.add_spool(material="pla", brand="A", color="White", weight_grams=1000)
        temp_inventory.add_spool(material="petg", brand="B", color="Black", weight_grams=500)

        summary = temp_inventory.get_inventory_summary()
        assert summary["total_spools"] == 2
        assert summary["total_weight_grams"] == 1500
        assert "pla" in summary["materials"]
        assert "petg" in summary["materials"]

    def test_estimate_usage(self, temp_inventory):
        """Test finding spools for print job."""
        temp_inventory.add_spool(material="pla", brand="A", color="White", weight_grams=100)
        temp_inventory.add_spool(material="pla", brand="B", color="Black", weight_grams=500)

        # Need 200g of PLA
        suitable = temp_inventory.estimate_usage(200, "pla")
        assert len(suitable) == 1
        assert suitable[0].weight_grams == 500

    def test_spool_remaining_meters(self, temp_inventory):
        """Test remaining meters calculation."""
        spool = temp_inventory.add_spool(
            material="pla",
            brand="A",
            color="White",
            weight_grams=1000,
        )
        # 1kg of PLA at 1.75mm diameter is roughly 330m
        assert spool.remaining_meters > 300
        assert spool.remaining_meters < 400
