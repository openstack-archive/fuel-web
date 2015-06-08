define([
    'intern!object',
    'intern/chai!assert',
    'underscore',
    'models',
    'expression',
    'expression/objects'
], function(registerSuite, assert, _, models, Expression, expressionObjects) {
    'use strict';

    registerSuite({
        'Expression parser test': function() {
            var hypervisor = 'kvm';
            var testModels = {
                cluster: new models.Cluster({mode: 'ha_compact'}),
                settings: new models.Settings({common: {libvirt_type: {value: hypervisor}}}),
                release: new models.Release({roles: ['controller', 'compute']})
            };
            var testCases = [
                // test scalars
                ['true', true],
                ['false', false],
                ['123', 123],
                ['"123"', '123'],
                ["'123'", '123'],
                // test null
                ['null', null],
                ['null == false', false],
                ['null == true', false],
                ['null == null', true],
                // test boolean operators
                ['true or false', true],
                ['true and false', false],
                ['not true', false],
                // test precedence
                ['true or true and false or false', true],
                ['true == true and false == false', true],
                // test comparison
                ['123 == 123', true],
                ['123 == 321', false],
                ['123 != 321', true],
                ['123 != "123"', true],
                // test grouping
                ['(true or true) and not (false or false)', true],
                // test errors
                ['(true', Error],
                ['false and', Error],
                ['== 123', Error],
                ['#^@$*()#@!', Error],
                // test modelpaths
                ['cluster:mode', 'ha_compact'],
                ['cluster:mode == "ha_compact"', true],
                ['cluster:mode != "multinode"', true],
                ['"controller" in release:roles', true],
                ['"unknown-role" in release:roles', false],
                ['settings:common.libvirt_type.value', hypervisor],
                ['settings:common.libvirt_type.value == "' + hypervisor + '"', true],
                ['cluster:mode == "ha_compact" and not (settings:common.libvirt_type.value != "' + hypervisor + '")', true],
                // test nonexistent keys
                ['cluster:nonexistentkey', Error],
                // test evaluation flow
                ['cluster:mode != "ha_compact" and cluster:nonexistentkey == 1', false],
                ['cluster:mode == "ha_compact" and cluster:nonexistentkey == 1', Error]
            ];

            function evaluate(expression) {
                var result = Expression(expression, testModels).evaluate();
                return result instanceof expressionObjects.ModelPath ? result.get() : result;
            }

            _.each(testCases, function(testCase) {
                var expression = testCase[0];
                var result = testCase[1];
                if (result === Error) {
                    assert.throws(evaluate.bind(null, expression), Error, '', expression + ' throws an error');
                } else {
                    assert.strictEqual(evaluate(expression), result, expression + ' evaluates correctly');
                }
            });
        }
    });
});
