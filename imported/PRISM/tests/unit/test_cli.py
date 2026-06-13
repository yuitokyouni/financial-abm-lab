"""Tests for CLI argument parsing, utility functions, and command dispatch."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prism.cli.main import (
    FACT_ALIASES,
    build_parser,
    main,
    resolve_fact_ids,
    resolve_ner_path,
)


class TestBuildParser:
    def test_returns_parser(self):
        parser = build_parser()
        assert parser.prog == "prism"

    def test_run_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(
            ["run", "--adapter", "sg", "--ner", "x.yaml", "--facts", "leverage"]
        )
        assert args.command == "run"
        assert args.adapter == "sg"
        assert args.seed == 42

    def test_tensor_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(
            ["tensor", "--adapters", "sg,ci", "--ners", "a.yaml,b.yaml", "--facts", "leverage"]
        )
        assert args.command == "tensor"
        assert args.adapters == "sg,ci"

    def test_compare_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(
            ["compare", "--adapter", "sg", "--ner", "x.yaml", "--facts", "leverage"]
        )
        assert args.command == "compare"
        assert args.methods is None

    def test_heatmap_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(
            ["heatmap", "--adapters", "sg", "--ners", "x.yaml", "--facts", "leverage"]
        )
        assert args.command == "heatmap"
        assert args.output == "heatmap.png"

    def test_latex_heatmap_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(
            ["latex-heatmap", "--adapters", "sg", "--ners", "x.yaml", "--facts", "leverage"]
        )
        assert args.command == "latex-heatmap"
        assert args.output == "heatmap.pdf"

    def test_latex_table_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(
            ["latex-table", "--adapters", "sg", "--ners", "x.yaml", "--facts", "leverage"]
        )
        assert args.command == "latex-table"
        assert args.output == "table.tex"

    def test_per_path_facts_flag(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "run",
                "--adapter",
                "sg",
                "--ner",
                "x.yaml",
                "--facts",
                "leverage",
                "--per-path-facts",
            ]
        )
        assert args.per_path_facts is True

    def test_real_data_flag(self):
        parser = build_parser()
        args = parser.parse_args(
            ["run", "--adapter", "sg", "--ner", "x.yaml", "--facts", "leverage", "--real-data"]
        )
        assert args.real_data is True

    def test_no_command_returns_none(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None


class TestResolvFactIds:
    def test_single_alias(self):
        assert resolve_fact_ids("leverage") == ["leverage_effect"]

    def test_multiple_aliases(self):
        result = resolve_fact_ids("leverage,volclust,gainloss")
        assert result == ["leverage_effect", "volatility_clustering", "gain_loss_asymmetry"]

    def test_passthrough_unknown(self):
        assert resolve_fact_ids("some_custom_fact") == ["some_custom_fact"]

    def test_full_name_passthrough(self):
        assert resolve_fact_ids("leverage_effect") == ["leverage_effect"]

    def test_all_aliases_present(self):
        expected_aliases = {
            "leverage",
            "volclust",
            "gainloss",
            "fattails",
            "absacf",
            "sqacf",
        }
        assert set(FACT_ALIASES.keys()) == expected_aliases

    def test_whitespace_handling(self):
        result = resolve_fact_ids("leverage , volclust")
        assert result == ["leverage_effect", "volatility_clustering"]


class TestResolveNerPath:
    def test_existing_file(self, tmp_path: Path):
        ner_file = tmp_path / "test.yaml"
        ner_file.write_text("test")
        assert resolve_ner_path(str(ner_file)) == ner_file

    def test_search_in_data_ner_dir(self, tmp_path: Path):
        ner_dir = tmp_path / "data" / "ner"
        ner_dir.mkdir(parents=True)
        ner_file = ner_dir / "my_ner.yaml"
        ner_file.write_text("test")
        import sys

        cli_mod = sys.modules["prism.cli.main"]
        original = cli_mod.NER_SEARCH_DIRS  # type: ignore[attr-defined]
        try:
            cli_mod.NER_SEARCH_DIRS = [ner_dir]  # type: ignore[attr-defined]
            assert resolve_ner_path("my_ner") == ner_file
        finally:
            cli_mod.NER_SEARCH_DIRS = original  # type: ignore[attr-defined]

    def test_not_found_raises(self):
        import sys

        cli_mod = sys.modules["prism.cli.main"]
        original = cli_mod.NER_SEARCH_DIRS  # type: ignore[attr-defined]
        try:
            cli_mod.NER_SEARCH_DIRS = []  # type: ignore[attr-defined]
            with pytest.raises(FileNotFoundError, match="NER not found"):
                resolve_ner_path("nonexistent_ner_xyz")
        finally:
            cli_mod.NER_SEARCH_DIRS = original  # type: ignore[attr-defined]


class TestMainNoCommand:
    def test_no_args_returns_1(self, capsys: pytest.CaptureFixture[str]):
        ret = main([])
        assert ret == 1
        captured = capsys.readouterr()
        assert "PRISM" in captured.out


class TestMainRunCommand:
    @patch("prism.cli.main.run_cell")
    def test_run_prints_summary(self, mock_run_cell: MagicMock, capsys: pytest.CaptureFixture[str]):
        mock_output = MagicMock()
        mock_output.summary.return_value = "Test summary output"
        mock_output.to_dict.return_value = {"test": True}
        mock_run_cell.return_value = mock_output

        ner_path = "data/ner/tspp_2016_us_equity.yaml"
        ret = main(["run", "--adapter", "sg", "--ner", ner_path, "--facts", "leverage"])
        assert ret == 0

        mock_run_cell.assert_called_once()
        call_kwargs = mock_run_cell.call_args
        assert call_kwargs.kwargs["adapter_name"] == "sg"
        assert call_kwargs.kwargs["fact_ids"] == ["leverage_effect"]

        captured = capsys.readouterr()
        assert "Test summary output" in captured.out

    @patch("prism.cli.main.run_cell")
    def test_run_with_output_file(self, mock_run_cell: MagicMock, tmp_path: Path):
        mock_output = MagicMock()
        mock_output.summary.return_value = "summary"
        mock_output.to_dict.return_value = {"key": "value"}
        mock_run_cell.return_value = mock_output

        out_file = tmp_path / "result.json"
        ner_path = "data/ner/tspp_2016_us_equity.yaml"
        ret = main(
            [
                "run",
                "--adapter",
                "sg",
                "--ner",
                ner_path,
                "--facts",
                "leverage",
                "--output",
                str(out_file),
            ]
        )
        assert ret == 0
        assert out_file.exists()
        data = json.loads(out_file.read_text())
        assert data == {"key": "value"}


class TestMainTensorCommand:
    @patch("prism.cli.main.run_tensor")
    def test_tensor_prints_summary(
        self, mock_run_tensor: MagicMock, capsys: pytest.CaptureFixture[str]
    ):
        mock_output = MagicMock()
        mock_output.summary.return_value = "Tensor summary"
        mock_output.to_dict.return_value = {"tensor": True}
        mock_run_tensor.return_value = mock_output

        ner_path = "data/ner/tspp_2016_us_equity.yaml"
        ret = main(
            [
                "tensor",
                "--adapters",
                "sg,ci",
                "--ners",
                f"{ner_path},{ner_path}",
                "--facts",
                "leverage,volclust",
            ]
        )
        assert ret == 0

        call_kwargs = mock_run_tensor.call_args
        assert call_kwargs.kwargs["adapter_names"] == ["sg", "ci"]
        assert call_kwargs.kwargs["fact_ids"] == [
            "leverage_effect",
            "volatility_clustering",
        ]

        captured = capsys.readouterr()
        assert "Tensor summary" in captured.out


class TestMainCompareCommand:
    @patch("prism.cli.main.compare_causal_methods")
    def test_compare_prints_summary(
        self, mock_compare: MagicMock, capsys: pytest.CaptureFixture[str]
    ):
        mock_output = MagicMock()
        mock_output.summary.return_value = "Compare summary"
        mock_output.to_dict.return_value = {"compare": True}
        mock_compare.return_value = mock_output

        ner_path = "data/ner/tspp_2016_us_equity.yaml"
        ret = main(
            [
                "compare",
                "--adapter",
                "sg",
                "--ner",
                ner_path,
                "--facts",
                "leverage",
            ]
        )
        assert ret == 0
        mock_compare.assert_called_once()
        assert mock_compare.call_args.kwargs["methods"] is None

        captured = capsys.readouterr()
        assert "Compare summary" in captured.out

    @patch("prism.cli.main.compare_causal_methods")
    def test_compare_with_methods(self, mock_compare: MagicMock):
        mock_output = MagicMock()
        mock_output.summary.return_value = "s"
        mock_output.to_dict.return_value = {}
        mock_compare.return_value = mock_output

        ner_path = "data/ner/tspp_2016_us_equity.yaml"
        main(
            [
                "compare",
                "--adapter",
                "sg",
                "--ner",
                ner_path,
                "--facts",
                "leverage",
                "--methods",
                "rct,did",
            ]
        )
        assert mock_compare.call_args.kwargs["methods"] == ["rct", "did"]


class TestMainHeatmapCommand:
    @patch("prism.cli.main.render_heatmap")
    @patch("prism.cli.main.run_tensor")
    def test_heatmap_creates_file(
        self,
        mock_run_tensor: MagicMock,
        mock_render: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        mock_output = MagicMock()
        mock_output.summary.return_value = "Heatmap tensor"
        mock_run_tensor.return_value = mock_output

        out_file = tmp_path / "test.png"
        ner_path = "data/ner/tspp_2016_us_equity.yaml"
        ret = main(
            [
                "heatmap",
                "--adapters",
                "sg",
                "--ners",
                ner_path,
                "--facts",
                "leverage",
                "--output",
                str(out_file),
            ]
        )
        assert ret == 0
        mock_render.assert_called_once_with(mock_output, output_path=out_file)

        captured = capsys.readouterr()
        assert "Heatmap written to" in captured.out


class TestMainLatexHeatmapCommand:
    @patch("prism.cli.main.render_latex_heatmap")
    @patch("prism.cli.main.run_tensor")
    def test_latex_heatmap(
        self,
        mock_run_tensor: MagicMock,
        mock_render: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        mock_output = MagicMock()
        mock_run_tensor.return_value = mock_output

        out_file = tmp_path / "test.pdf"
        ner_path = "data/ner/tspp_2016_us_equity.yaml"
        ret = main(
            [
                "latex-heatmap",
                "--adapters",
                "sg",
                "--ners",
                ner_path,
                "--facts",
                "leverage",
                "--output",
                str(out_file),
            ]
        )
        assert ret == 0
        mock_render.assert_called_once()

        captured = capsys.readouterr()
        assert "LaTeX heatmap written to" in captured.out


class TestMainLatexTableCommand:
    @patch("prism.cli.main.export_latex_table")
    @patch("prism.cli.main.run_tensor")
    def test_latex_table(
        self,
        mock_run_tensor: MagicMock,
        mock_export: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ):
        mock_output = MagicMock()
        mock_run_tensor.return_value = mock_output
        mock_export.return_value = "\\begin{table}...\\end{table}"

        out_file = tmp_path / "test.tex"
        ner_path = "data/ner/tspp_2016_us_equity.yaml"
        ret = main(
            [
                "latex-table",
                "--adapters",
                "sg",
                "--ners",
                ner_path,
                "--facts",
                "leverage",
                "--output",
                str(out_file),
            ]
        )
        assert ret == 0
        mock_export.assert_called_once()

        captured = capsys.readouterr()
        assert "LaTeX table written to" in captured.out
        assert "\\begin{table}" in captured.out
