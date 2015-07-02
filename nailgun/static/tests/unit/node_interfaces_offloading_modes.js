define([
    'intern!object',
    'intern/chai!assert',
    'underscore',
    'sinon',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/offloading_modes_control'
], function(registerSuite, assert, _, sinon, OffloadingModes) {
    'use strict';

    var offloadingModesConrol,
        TestMode22,
        TestMode31,
        fakeOffloadingModes,
        fakeInterface = {
            offloading_modes: fakeOffloadingModes,
            get: function(key) {
                assert.equal(key, 'offloading_modes', '"offloading_modes" interface property should be used to get data');
                return fakeOffloadingModes;
            },
            set: function(key, value) {
                assert.equal(key, 'offloading_modes', '"offloading_modes" interface property should be used to set data');
                fakeOffloadingModes = value;
            }
        };

    registerSuite({
        name: 'Offloadning Modes control',

        beforeEach: function() {
            TestMode22 = {name: 'TestName22', state: false, sub: []};
            TestMode31 = {name: 'TestName31', state: null, sub: []};
            fakeOffloadingModes = [
                {
                    name: 'TestName1',
                    state: true,
                    sub: [
                        {name: 'TestName11', state: true, sub: [
                            TestMode31
                        ]},
                        {name: 'TestName12', state: false, sub: []},
                        {name: 'TestName13', state: null, sub: []}
                    ]
                },
                {
                    name: 'TestName2',
                    state: false,
                    sub: [
                        {name: 'TestName21', state: false, sub: []},
                        TestMode22,
                        {name: 'TestName23', state: false, sub: []}
                    ]
                }
            ];
            offloadingModesConrol = new OffloadingModes({
                interface: fakeInterface
            });
        },
        'Finding mode by name': function() {
            var mode = offloadingModesConrol.findMode(TestMode22.name, fakeOffloadingModes);
            assert.deepEqual(mode, TestMode22, 'Mode can be found by name');
        },
        'Set mode state logic': function() {
            offloadingModesConrol.setModeState(TestMode31, true);
            assert.strictEqual(TestMode31.state, true, 'Mode state is changing');
        },
        'Set submodes states logic': function() {
            var mode = offloadingModesConrol.findMode('TestName1', fakeOffloadingModes);
            offloadingModesConrol.setModeState(mode, false);
            assert.strictEqual(TestMode31.state, false, 'Parent state changing leads to all child modes states changing');
        },
        'Disabled reversed logic': function() {
            var mode = offloadingModesConrol.findMode('TestName2', fakeOffloadingModes);
            offloadingModesConrol.setModeState(TestMode22, true);
            offloadingModesConrol.checkModes(null, fakeOffloadingModes);
            assert.strictEqual(mode.state, null, 'Parent state changing leads to all child modes states changing');
        }
    });
});
