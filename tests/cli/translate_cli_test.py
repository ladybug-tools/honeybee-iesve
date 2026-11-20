"""Test the CLI commands that translate models to/from GEM."""
import os
from click.testing import CliRunner
from honeybee_iesve.cli.translate import model_to_gem_cli, model_from_gem_cli


def test_model_to_from_gem():
    runner = CliRunner()
    input_hb_model = './tests/assets/sample_model_45.hbjson'
    project_info = './tests/assets/project_info.json'
    output_file = './tests/assets/sample_model_45.gem'

    in_args = [input_hb_model, '--project-info', project_info, '--output-file', output_file]
    result = runner.invoke(model_to_gem_cli, in_args)
    assert result.exit_code == 0
    assert os.path.isfile(output_file)

    re_exported_file = './tests/assets/sample_model_45_2.hbjson'
    result = runner.invoke(model_from_gem_cli, [output_file, '--output-file', re_exported_file])
    assert result.exit_code == 0

    os.remove(output_file)
    os.remove(re_exported_file)
