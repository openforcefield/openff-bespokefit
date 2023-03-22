from pathlib import Path

import pytest

from openff.bespokefit.utilities.tempcd import temporary_cd


@pytest.mark.parametrize(
    "path",
    [
        "tempcd_test",
        Path("tempcd_test"),
        None,
        ".",
        "",
    ],
)
class TestTemporaryCD:
    @pytest.fixture(autouse=True)
    def run_test_in_empty_temporary_directory(self, monkeypatch, tmp_path):
        """
        Tests in this class should run in their own empty temporary directories

        This fixture creates a temporary directory for the test, moves into it,
        and deletes it when the test is finished.
        """
        monkeypatch.chdir(tmp_path)

    def test_tempcd_changes_dir(self, path):
        """
        Check temporary_cd changes directory to the target directory
        """
        # Arrange
        starting_path = Path(".").resolve()

        # Act
        with temporary_cd(path):
            temp_path = Path(".").resolve()

        # Assert
        if path is None:
            assert temp_path.parent == starting_path
        else:
            assert temp_path == (starting_path / path).resolve()

    def test_tempcd_changes_back(self, path):
        """
        Check temporary_cd returns to original directory when context manager exits
        """
        # Arrange
        starting_path = Path(".").resolve()

        # Act
        with temporary_cd(path):
            pass

        # Assert
        assert Path(".").resolve() == starting_path

    def test_tempcd_cleans_up_temporary_directory(self, path, monkeypatch):
        """
        Check temporary_cd cleans up temporary directories it creates when
        BEFLOW_KEEP_TMP_FILES is not set

        This test is skipped when it is parametrized to operate on the working
        directory because the working directory must exist and therefore cannot
        be a temporary directory. This check is hard-coded to check for the
        path being ``"."`` or ``""``, rather than simply checking if the path
        exists, so that conflicts between runs will be detected (though such
        conflicts should be prevented by the
        ``run_test_in_empty_temporary_directory`` fixture)
        """
        if path in [".", ""]:
            pytest.skip("'Temporary' directory exists")

        # Arrange
        monkeypatch.delenv("BEFLOW_KEEP_TMP_FILES", raising=False)

        # Act
        with temporary_cd(path):
            Path("touch").write_text("Ensure cleanup of directories with files")
            temp_path = Path(".").resolve()

        # Assert
        assert not temp_path.exists()

    def test_tempcd_keeps_temporary_directory(self, path, monkeypatch):
        """
        Check temporary_cd keeps temporary directories it creates when
        BEFLOW_KEEP_TMP_FILES is set
        """
        # Arrange
        monkeypatch.setenv("BEFLOW_KEEP_TMP_FILES", "1")

        # Act
        with temporary_cd(path):
            temp_path = Path(".").resolve()

        # Assert
        assert temp_path.exists()

    @pytest.mark.parametrize("keep_tmp_files", [True, False])
    def test_tempcd_keeps_existing_directory(self, path, monkeypatch, keep_tmp_files):
        """
        Check temporary_cd keeps existing directories

        This test is skipped when the path is ``None`` because it guarantees
        that the path does not exist. The target directory will be created in
        the Arrange section, unless it is the working directory (in which case
        it already exists). This test is hard-coded to check for the path being
        ``"."`` or ``""``, rather than simply checking if the path exists, so
        that conflicts between runs will be detected (though such conflicts
        should be prevented by the ``run_test_in_empty_temporary_directory``
        fixture)
        """
        if path is None:
            pytest.skip("Temporary directory is guaranteed not to exist")

        # Arrange
        if path not in [".", ""]:
            Path(path).mkdir()
        if keep_tmp_files:
            monkeypatch.setenv("BEFLOW_KEEP_TMP_FILES", "1")
        else:
            monkeypatch.delenv("BEFLOW_KEEP_TMP_FILES", raising=False)

        # Act
        with temporary_cd(path):
            pass

        # Assert
        assert Path(path).is_dir()
