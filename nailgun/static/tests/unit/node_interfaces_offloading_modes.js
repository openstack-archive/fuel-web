define([
    'intern!object',
    'intern/chai!assert',
    'underscore',
    'sinon',
    'jsx!views/cluster_page_tabs/nodes_tab_screens/offloading_modes_control'
], function(registerSuite, assert, _, sinon, OffloadingModes) {
    'use strict';

    var offloadingModesConrol,
        bb,
        ca,
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
            bb = {name: 'bb', state: false, sub: []};
            ca = {name: 'ca', state: null, sub: []};
            fakeOffloadingModes = [
                {
                    name: 'a',
                    state: true,
                    sub: [
                        {name: 'aa', state: true, sub: [
                            ca
                        ]},
                        {name: 'ab', state: false, sub: []},
                        {name: 'ac', state: null, sub: []}
                    ]
                },
                {
                    name: 'b',
                    state: false,
                    sub: [
                        {name: 'ba', state: false, sub: []},
                        bb,
                        {name: 'bc', state: false, sub: []}
                    ]
                }
            ];
            offloadingModesConrol = new OffloadingModes({
                interface: fakeInterface
            });
        },
        'Finding mode by name': function() {
            var mode = offloadingModesConrol.findMode(bb.name, fakeOffloadingModes);
            assert.deepEqual(mode, bb, 'Mode can be found by name');
        },
        'Set mode state logic': function() {
            offloadingModesConrol.setModeState(ca, true);
            assert.strictEqual(ca.state, true, 'Node state is changing');
        },
        'Set submodes states logic': function() {
            var mode = offloadingModesConrol.findMode('a', fakeOffloadingModes);
            offloadingModesConrol.setModeState(mode, false);
            assert.strictEqual(ca.state, false, 'Parent state changing leads to all child modes states changing');
        },
        'Disabled reversed logic': function() {
            var mode = offloadingModesConrol.findMode('b', fakeOffloadingModes);
            offloadingModesConrol.setModeState(bb, true);
            offloadingModesConrol.checkModes(null, fakeOffloadingModes);
            assert.strictEqual(mode.state, null, 'Parent state changing leads to all child modes states changing');
        },
        'Mode state rotation logic': function() {
            assert.strictEqual(bb.state, false, 'Initial state is false');
            var mode,
                last = false,
                rotate = offloadingModesConrol.rotateModeState(bb.name);

            [null, true, false].forEach(function(state) {
                rotate();
                mode = offloadingModesConrol.findMode('bb', fakeOffloadingModes);
                assert.strictEqual(mode.state, state, 'State expected to change from ' + last + ' to ' + state);
                last = state;
            });
        }
    });
});
