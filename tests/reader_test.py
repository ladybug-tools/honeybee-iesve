"""Test the functions in the reader module that create Honeybee Models from GEM."""
from honeybee_iesve.reader import model_from_gem


def test_underground_aperture():
    in_file = './tests/assets/room_underground.gem'
    with open(in_file, 'r') as gf:
        model = model_from_gem(gf.read())
    assert len(model.rooms) == 2


def test_topo_shade():
    in_file = './tests/assets/topographical_shade.gem'
    with open(in_file, 'r') as gf:
        model = model_from_gem(gf.read())
    assert len(model.shades) == 6


def test_translucent_shade():
    in_file = './tests/assets/translucent_shade.gem'
    with open(in_file, 'r') as gf:
        model = model_from_gem(gf.read())
    assert len(model.shades) == 1


def test_tree():
    in_file = './tests/assets/tree.gem'
    with open(in_file, 'r') as gf:
        model = model_from_gem(gf.read())
    assert len(model.shades) == 10


def test_pv():
    in_file = './tests/assets/pv.gem'
    with open(in_file, 'r') as gf:
        model = model_from_gem(gf.read())
    assert len(model.shades) == 1


def test_non_ascii():
    in_file = './tests/assets/room_non_ascii.gem'
    with open(in_file, 'r', encoding='utf-8') as gf:
        model = model_from_gem(gf.read())
    assert model.rooms[0].display_name == 'اتاق خواب'
