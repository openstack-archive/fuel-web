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

suite('Custom Hugepages control', () => {
  setup(() => {
    var renderControl = function(config, error) {
      return ReactTestUtils.renderIntoDocument(
        <customControls.custom_hugepages
          config={config}
          onChange={sinon.spy()}
          name='hugepages.nova'
          error={error || null}
          disabled={false}
        />
      );
    };
    var config = {};
    config.value = {'0M': 0, '1GB': 2};
    control1 = renderControl(config);
    control2 = renderControl(config, 'Invalid data');
    config.value = {};
    control3 = renderControl(config);
  });

  test('Test control render', () => {
    assert.equal(
      ReactTestUtils.scryRenderedDOMComponentsWithTag(control1, 'input').length,
      2,
      'Two text inputs are rendered'
    );

    assert.equal(
      ReactTestUtils.scryRenderedDOMComponentsWithClass(control2, 'error').length,
      1,
      'Validation error is shown for control input'
    );

    assert.equal(
      ReactTestUtils.scryRenderedDOMComponentsWithClass(control3, 'huge-pages').length,
      0,
      'Component is not rendered in case of empty values'
    );
  });

  test('Test control value change', () => {
    var input = control1.refs.input0;
    input.value = '1';
    ReactTestUtils.Simulate.change(input);
    assert.deepEqual(
      control1.props.onChange.args[0][1],
      ['1', '2'],
      'Control value is changed'
    );
  });

});
