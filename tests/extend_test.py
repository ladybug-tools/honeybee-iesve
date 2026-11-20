"""Tests the features that honeybee_iesve adds to honeybee_core Model."""
from honeybee.model import Model
from honeybee_iesve.properties.model import ModelIesveProperties
from honeybee_iesve.writer import model_to_gem


def test_model_extend():
    # serialize the model
    in_file = './tests/assets/sample_model_45.hbjson'
    model = Model.from_hbjson(in_file)

    # check that the model has properties and can be validated
    assert hasattr(model.properties, 'iesve')
    assert isinstance(model.properties.iesve, ModelIesveProperties)
    assert isinstance(model.properties.iesve.host, Model)
    assert model.check_for_extension('iesve', raise_exception=False) == ''

    # check that the model can be translated to GEM
    gem_str = model_to_gem(model)
    assert isinstance(gem_str, str)
