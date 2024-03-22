import os

from openff.bespokefit.executor.services import Settings


class TestSettings:
    def test_fragmenter_settings(self):
        settings = Settings(
            BEFLOW_FRAGMENTER_WORKER="fragmenter.module",
            BEFLOW_FRAGMENTER_WORKER_N_CORES=2,
            BEFLOW_FRAGMENTER_WORKER_MAX_MEM=3.4,
        )

        assert settings.fragmenter_settings.import_path == "fragmenter.module"
        assert settings.fragmenter_settings.n_cores == 2
        assert settings.fragmenter_settings.max_memory == 3.4

    def test_qc_compute_settings(self):
        settings = Settings(
            BEFLOW_QC_COMPUTE_WORKER="qc_compute.module",
            BEFLOW_QC_COMPUTE_WORKER_N_CORES=2,
            BEFLOW_QC_COMPUTE_WORKER_MAX_MEM=3.4,
        )

        assert settings.qc_compute_settings.import_path == "qc_compute.module"
        assert settings.qc_compute_settings.n_cores == 2
        assert settings.qc_compute_settings.max_memory == 3.4

    def test_optimizer_settings(self):
        settings = Settings(
            BEFLOW_OPTIMIZER_WORKER="optimizer.module",
            BEFLOW_OPTIMIZER_WORKER_N_CORES=2,
            BEFLOW_OPTIMIZER_WORKER_MAX_MEM=3.4,
        )

        assert settings.optimizer_settings.import_path == "optimizer.module"
        assert settings.optimizer_settings.n_cores == 2
        assert settings.optimizer_settings.max_memory == 3.4

    def test_apply_env(self):
        assert "BEFLOW_API_V1_STR" not in os.environ

        with Settings().apply_env():
            assert "BEFLOW_API_V1_STR" in os.environ

        assert "BEFLOW_API_V1_STR" not in os.environ
