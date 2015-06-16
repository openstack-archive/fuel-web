define([
    'intern!object',
    'intern/chai!assert',
    'underscore',
    'sinon'
], function(registerSuite, assert, _, sinon) {
    'use strict';

    var input;

    registerSuite({
        name: 'File Control',

        beforeEach: function() {
            var controls = require('views/controls');

            input = new controls.Input({
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
        },

        Initialization: function() {
            var initialState = input.getInitialState();

            assert.equal(input.props.type, 'file', 'Input type should be equal to file');
            assert.equal(initialState.fileName, 'certificate.crt', 'Default file name must correspond to provided one');
            assert.equal(initialState.content, 'CERTIFICATE', 'Content should be equal to the default');
        },

        'File selection': function() {
            var clickSpy = sinon.spy();

            sinon.stub(input, 'getInputDOMNode').returns({
                click: clickSpy
            });

            input.pickFile();
            assert.ok(clickSpy.calledOnce, 'When icon clicked input control should be clicked too to open select file dialog');
        },

        'File fetching': function() {
            var readMethod = sinon.mock(),
                readerObject = {
                    readAsBinaryString: readMethod,
                    result: 'File contents'
                },
                saveMethod = sinon.spy(input, 'saveFile');

            window.FileReader = function() {return readerObject};

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
        },

        'File saving': function() {
            var setState = sinon.spy(input, 'setState'),
                dummyName = 'dummy.ext',
                dummyContent = 'Lorem ipsum dolores';
            input.saveFile(dummyName, dummyContent);

            assert.deepEqual(setState.args[0][0], {
                fileName: dummyName,
                content: dummyContent
            }, 'Save file must update control state with data supplied');

            assert.deepEqual(input.props.onChange.args[0][1], {
                name: dummyName,
                content: dummyContent
            }, 'Control sends updated data upon changes');
        }
    });
});
