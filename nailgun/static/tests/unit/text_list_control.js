/*
 * Copyright 2016 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 **/

import React from 'react';
import ReactTestUtils from 'react-addons-test-utils';
import customControls from 'views/custom_controls';

var control1, control2, control3;

suite('Text_list Control', () => {
  setup(() => {
    var renderControl = function(value, error) {
      return ReactTestUtils.renderIntoDocument(
        <customControls.text_list
          type='text_list'
          name='some_name'
          value={value}
          label='Some label'
          description='Some description'
          disabled={false}
          onChange={sinon.spy()}
          error={error || null}
          min={2}
          max={4}
        />
      );
    };
    control1 = renderControl(['val1', 'val2']);
    control2 = renderControl(['val1', 'val2', 'val3']);
    control3 = renderControl(['val1', 'val2', 'val3', 'val4'], [null, 'Invalid data', null, null]);
  });

  test('Test control render', () => {
    assert.equal(
      control1.props.min,
      2,
      'Min prop should be equal to 2 instead of default 1'
    );
    assert.equal(
      control1.props.max,
      4,
      'Max prop should be equal to 4 instead of default null'
    );
    assert.equal(
      ReactTestUtils.scryRenderedDOMComponentsWithTag(control1, 'input').length,
      2,
      'Two text inputs are rendered'
    );
    assert.equal(
      ReactTestUtils.scryRenderedDOMComponentsWithClass(control1, 'field-description').length,
      1,
      'Control description is shown'
    );

    var checkInputButtons = function(control, addFieldButtonsAmount, removeFieldButtonsAmount) {
      assert.equal(
        ReactTestUtils.scryRenderedDOMComponentsWithClass(control, 'btn-add-field').length,
        addFieldButtonsAmount,
        'Add Field buttons amount: ' + addFieldButtonsAmount
      );
      assert.equal(
        ReactTestUtils.scryRenderedDOMComponentsWithClass(control, 'btn-remove-field').length,
        removeFieldButtonsAmount,
        'Remove Field buttons amount: ' + removeFieldButtonsAmount
      );
    };

    // maximum inputs amount is not reached, so 2 plus buttons expected
    // minimum inputs amount is reached, so no minus buttons expected
    checkInputButtons(control1, 2, 0);

    // maximum inputs amount is not reached, so 3 plus buttons expected
    // minimum inputs amount is not reached, so 3 minus buttons expected
    checkInputButtons(control2, 3, 3);

    // maximum inputs amount is reached, so no plus buttons expected
    // minimum inputs amount is not reached, so 4 minus buttons expected
    checkInputButtons(control3, 0, 4);

    assert.equal(
      ReactTestUtils.scryRenderedDOMComponentsWithClass(control3, 'field-description').length,
      0,
      'Control description is not shown in case of validation errors'
    );
    assert.equal(
      ReactTestUtils.scryRenderedDOMComponentsWithClass(control3, 'field-error').length,
      1,
      'Validation error is shown for control input'
    );
  });

  test('Test control value change', () => {
    var input = control1.refs.input0;
    input.value = 'val1_new';
    ReactTestUtils.Simulate.change(input);
    assert.deepEqual(
      control1.props.onChange.args[0][1],
      ['val1_new', 'val2'],
      'Control value is changed'
    );

    ReactTestUtils.Simulate.click(control1.refs.add0);
    assert.deepEqual(
      control1.props.onChange.args[1][1],
      ['val1', '', 'val2'],
      'New control value is added'
    );

    ReactTestUtils.Simulate.click(control2.refs.remove0);
    assert.deepEqual(
      control2.props.onChange.args[0][1],
      ['val2', 'val3'],
      'The first control value is removed'
    );
  });

  test('Test control validation', () => {
    var validateControl = function(value) {
      return customControls.text_list.validate({
        value: value,
        regex: {source: '^[a-z]+$', error: 'Invalid data'}
      });
    };
    assert.equal(
      validateControl(['abc']),
      null,
      'Control has valid value'
    );
    assert.deepEqual(
      validateControl(['abc', '', '123']),
      [null, 'Invalid data', 'Invalid data'],
      'Control has invalid value'
    );
  });
});
