/*
 * Copyright 2015 Mirantis, Inc.
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
import {Input} from 'views/controls';

var input;
suite('File Control', () => {
  setup(() => {
    input = new Input({
      type: 'file',
      name: 'some_file',
      label: 'Please select some file',
      description: 'File should be selected from the local disk',
      disabled: false,
      onChange: sinon.spy(),
      defaultValue: {
        name: 'certificate.crt',
        content: 'CERTIFICATE'
      }
    });
  });

  test('Initialization', () => {
    var initialState = input.getInitialState();

    assert.equal(input.props.type, 'file', 'Input type should be equal to file');
    assert.equal(initialState.fileName, 'certificate.crt',
      'Default file name must correspond to provided one');
    assert.equal(initialState.content, 'CERTIFICATE', 'Content should be equal to the default');
  });

  test('File selection', () => {
    var clickSpy = sinon.spy();

    sinon.stub(input, 'getInputDOMNode').returns({
      click: clickSpy
    });

    input.pickFile();
    assert.ok(clickSpy.calledOnce,
      'When icon clicked input control should be clicked too to open select file dialog');
  });

  test('File fetching', () => {
    var readMethod = sinon.mock();
    var readerObject = {
      readAsBinaryString: readMethod,
      result: 'File contents'
    };
    var saveMethod = sinon.spy(input, 'saveFile');

    window.FileReader = () => readerObject;

    sinon.stub(input, 'getInputDOMNode').returns({
      value: '/dummy/path/to/somefile.ext',
      files: ['file1']
    });

    input.readFile();

    assert.ok(readMethod.calledOnce, 'File reading as binary expected to be executed once');
    sinon.assert.calledWith(readMethod, 'file1');

    readerObject.onload();
    assert.ok(saveMethod.calledOnce, 'saveFile handler called once');
    sinon.assert.calledWith(saveMethod, 'somefile.ext', 'File contents');
  });

  test('File saving', () => {
    var setState = sinon.spy(input, 'setState');
    var dummyName = 'dummy.ext';
    var dummyContent = 'Lorem ipsum dolores';
    input.saveFile(dummyName, dummyContent);

    assert.deepEqual(setState.args[0][0], {
      fileName: dummyName,
      content: dummyContent
    }, 'Save file must update control state with data supplied');

    assert.deepEqual(input.props.onChange.args[0][1], {
      name: dummyName,
      content: dummyContent
    }, 'Control sends updated data upon changes');
  });
});
