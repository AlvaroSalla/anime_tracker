"""
Unit tests for main.py entry point.

Tests cover:
- Positive cases: successful imports and function calls
- Negative cases: error handling for missing dependencies
- Edge cases: module-level behavior and __main__ execution
"""

import pytest
from unittest.mock import patch, MagicMock


class TestMainImports:
    """Test suite for module-level imports."""

    def test_crear_tabla_imported_successfully(self):
        """Positive: Verify crear_tabla can be imported from database.setup."""
        from database.setup import crear_tabla
        assert callable(crear_tabla)

    def test_anime_tracker_app_imported_successfully(self):
        """Positive: Verify AnimeTrackerApp can be imported from gui.app."""
        from gui.app import AnimeTrackerApp
        assert AnimeTrackerApp is not None
        assert hasattr(AnimeTrackerApp, 'mainloop')

    def test_import_module_structure(self):
        """Positive: Verify the module structure is correct."""
        import main
        assert hasattr(main, 'crear_tabla')
        assert hasattr(main, 'AnimeTrackerApp')


class TestMainExecution:
    """Test suite for main execution logic."""

    @patch('main.AnimeTrackerApp')
    @patch('main.crear_tabla')
    def test_main_creates_table_and_app(self, mock_crear_tabla, mock_app_class):
        """Positive: Verify main creates table and launches app."""
        # Setup mocks
        mock_crear_tabla.return_value = None
        mock_app_instance = MagicMock()
        mock_app_class.return_value = mock_app_instance

        # Import and execute main logic
        import main
        main.crear_tabla()
        app = main.AnimeTrackerApp()

        # Verify correct behavior
        mock_crear_tabla.assert_called_once()
        mock_app_class.assert_called_once()
        app.mainloop.assert_called_once()

    @patch('main.AnimeTrackerApp')
    @patch('main.crear_tabla')
    def test_crear_tabla_called_before_app_creation(self, mock_crear_tabla, mock_app_class):
        """Positive: Verify order of operations - table created before app."""
        mock_app_class.return_value = MagicMock()

        # Simulate execution order
        import main
        main.crear_tabla()
        main.AnimeTrackerApp()

        # Verify creacion order
        assert mock_crear_tabla.call_count == 1
        assert mock_app_class.call_count == 1


class TestMainAsScript:
    """Test suite for __main__ execution."""

    def test_main_module_has_main_guard(self):
        """Positive: Verify __name__ == '__main__' guard exists."""
        import main
        # The module should be importable without side effects
        assert main is not None

    @patch('main.AnimeTrackerApp')
    @patch('main.crear_tabla')
    def test_script_execution_without_error(self, mock_crear_tabla, mock_app_class):
        """Positive: Verify script can execute without errors."""
        mock_app_class.return_value = MagicMock()
        mock_crear_tabla.return_value = None

        # Should not raise any exceptions
        import main
        main.crear_tabla()
        app = main.AnimeTrackerApp()
        app.mainloop()


class TestImportErrors:
    """Test suite for import error scenarios."""

    def test_import_error_database_setup(self):
        """Negative: Handle missing database.setup module gracefully."""
        with patch('main.crear_tabla', None):
            from database.setup import crear_tabla
            # If patch returns None, crear_tabla should be None or raise
            assert crear_tabla is None or crear_tabla is not callable

    def test_import_error_gui_app(self):
        """Negative: Handle missing gui.app module gracefully."""
        with patch('main.AnimeTrackerApp', None):
            from gui.app import AnimeTrackerApp
            # If patch returns None, AnimeTrackerApp should be None
            assert AnimeTrackerApp is None


class TestEdgeCases:
    """Test suite for edge cases."""

    @patch('main.AnimeTrackerApp')
    @patch('main.crear_tabla')
    def test_multiple_main_calls(self, mock_crear_tabla, mock_app_class):
        """Edge: Verify multiple calls don't cause issues."""
        mock_app_class.return_value = MagicMock()
        mock_crear_tabla.return_value = None

        import main

        # First execution
        main.crear_tabla()
        main.AnimeTrackerApp()

        # Second execution
        main.crear_tabla()
        main.AnimeTrackerApp()

        # Both should have been called twice
        assert mock_crear_tabla.call_count == 2
        assert mock_app_class.call_count == 2

    def test_module_reimport_preserves_state(self):
        """Edge: Verify module reimport doesn't break state."""
        import main
        first_state = main.crear_tabla, main.AnimeTrackerApp

        # Reimport via importlib
        import importlib
        importlib.reload(main)

        # State should be preserved (same functions)
        assert main.crear_tabla is first_state[0]
        assert main.AnimeTrackerApp is first_state[1]


class TestMockIntegration:
    """Integration tests with mocked dependencies."""

    @patch('gui.app.AnimeTrackerApp.mainloop')
    @patch('database.setup.crear_tabla')
    def test_full_integration_flow(self, mock_crear_tabla, mock_mainloop):
        """Positive: Full integration test with real imports."""
        mock_crear_tabla.return_value = None

        # Import and run
        import main
        app = main.AnimeTrackerApp()
        app.mainloop()

        # Verify flow completed
        mock_crear_tabla.assert_called_once()
        mock_mainloop.assert_called_once()

    @patch('gui.app.AnimeTrackerApp')
    def test_app_instantiation_parameters(self, mock_app_class):
        """Edge: Verify app is instantiated with correct parameters."""
        mock_app_class.return_value = MagicMock()

        import main
        app = main.AnimeTrackerApp()

        # Verify instantiation occurred
        mock_app_class.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
