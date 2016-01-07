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
/*eslint object-shorthand: 0*/
define(['views/cluster_page_tabs/nodes_tab_screens/offloading_modes_control'], function(OffloadingModes) {
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

    suite('Offloadning Modes control', function() {
        setup(function() {
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
        });

        test('Finding mode by name', function() {
            var mode = offloadingModesConrol.findMode(TestMode22.name, fakeOffloadingModes);
            assert.deepEqual(mode, TestMode22, 'Mode can be found by name');
        });
        test('Set mode state logic', function() {
            offloadingModesConrol.setModeState(TestMode31, true);
            assert.strictEqual(TestMode31.state, true, 'Mode state is changing');
        });
        test('Set submodes states logic', function() {
            var mode = offloadingModesConrol.findMode('TestName1', fakeOffloadingModes);
            offloadingModesConrol.setModeState(mode, false);
            assert.strictEqual(TestMode31.state, false, 'Parent state changing leads to all child modes states changing');
        });
        test('Disabled reversed logic', function() {
            var mode = offloadingModesConrol.findMode('TestName2', fakeOffloadingModes);
            offloadingModesConrol.setModeState(TestMode22, true);
            offloadingModesConrol.checkModes(null, fakeOffloadingModes);
            assert.strictEqual(mode.state, null, 'Parent state changing leads to all child modes states changing');
        });
        test('All Modes option logic', function() {
            var enableAllModes = offloadingModesConrol.onModeStateChange('All Modes', true);
            enableAllModes();
            var mode = offloadingModesConrol.findMode('TestName2', fakeOffloadingModes);
            assert.strictEqual(mode.state, true, 'All Modes option state changing leads to all parent modes states changing');
        });
    });
});
