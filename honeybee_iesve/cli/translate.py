"""honeybee iesve translation commands."""
import click
import os
import io
import sys
import logging
import json

from ladybug.commandutil import process_content_to_output
from ladybug.projectinfo import ProjectInfo
from honeybee.model import Model
from honeybee.typing import clean_string
from honeybee_iesve.writer import model_to_gem as model_to_gem_str
from honeybee_iesve.reader import model_from_gem as model_from_gem_str

_logger = logging.getLogger(__name__)


@click.group(help='Commands for translating Honeybee JSON files to and from IES files.')
def translate():
    pass


@translate.command('model-to-gem')
@click.argument('model-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--project-info', '-pi', help='Full path to a ladybug ProjectInfo JSON that '
    'describes criteria about the project site. When specified, this will result in the '
    'north and location written into the GEM.', default=None, show_default=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--output-file', '-f', help='Optional GEM file path to output the GEM string '
    'of the translation. By default this will be printed out to stdout.',
    type=click.File('w'), default='-', show_default=True)
def model_to_gem_cli(model_file, project_info, output_file):
    """Translate a Model JSON file to an IES GEM file.
    \b

    Args:
        model_file: Full path to a Model JSON file (HBJSON) or a Model pkl (HBpkl) file.
    """
    try:
        model_to_gem(model_file, project_info, output_file)
    except Exception as e:
        _logger.exception('Model translation failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def model_to_gem(model_file, project_info=None, output_file=None):
    """Translate a Model JSON file to an IES GEM file.

    Args:
        model_file: Full path to a Honeybee Model file (HBJSON or HBpkl).
        project_info: Full path to a ladybug ProjectInfo JSON that describes
            criteria about the project site. When specified, this will result
            in the north and location written into the GEM.
        output_file: Optional GEM file path to output the GEM string of the
            translation. If None, the string will be returned from this function.
    """
    model = Model.from_file(model_file)
    if project_info is not None:
        project_info = ProjectInfo.from_json(project_info)
    gem_str = model_to_gem_str(model, project_info=project_info)
    return process_content_to_output(gem_str, output_file)


@translate.command('model-from-gem')
@click.argument('gem-file', type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@click.option(
    '--output-file', '-o', help='Optional HBJSON file path to output the HBJSON string '
    'of the translation. By default this will be printed out to stdout.',
    type=click.File('w'), default='-', show_default=True)
def model_from_gem_cli(gem_file, output_file):
    """Translate an IES GEM file to a HBJSON model.
    \b

    Args:
        gem-file: Full path to an IES VE GEM file.
    """
    try:
        model_from_gem(gem_file, output_file)
    except Exception as e:
        _logger.exception('Model translation failed.\n{}'.format(e))
        sys.exit(1)
    else:
        sys.exit(0)


def model_from_gem(gem_file, output_file=None):
    """Translate an IES GEM file to a HBJSON model.

    Args:
        gem_file: Full path to an IES VE GEM file.
        output_file: Optional HBJSON file path to output the JSON string of the
            translation. If None, the string will be returned from this function.
    """
    with io.open(gem_file, 'r', encoding='utf-8') as gf:
        file_contents = gf.read()
    model_name = os.path.basename(gem_file)
    if model_name.lower().endswith('.gem'):
        model_name = model_name[:-4]
    model = model_from_gem_str(file_contents, clean_string(model_name), model_name)
    content_str = json.dumps(model.to_dict())
    return process_content_to_output(content_str, output_file)
