/*
 * Copyright 2014 Mirantis, Inc.
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
define(['jquery', 'underscore', 'react', 'utils', 'jsx!views/controls'], function($, _, React, utils, controls) {
    'use strict';

    return {
        saveSettings: function(e) {
            //TODO: implement statistics settings saving
            e.preventDefault();
            if (this.state.personalizeStatistics && this.validateContacts()) return (new $.Deferred()).reject();
            this.setState({actionInProgress: true});
            var userData = {};
            _.each(this.refs, function(control, key) {
                var input = control.getInput();
                userData[key] = input.type == 'checkbox' ? input.checked : input.value;
            });
            return (new $.Deferred()).resolve();
        },
        validateContacts: function() {
            var errors = _.compact(_.map(['name', 'email', 'company'], function(data) {
                if (this.refs[data].getInput().value == '') return data;
            }, this));
            this.setState({errors: errors});
            return !!errors.length;
        },
        updateStates: function() {
            var sendStatistics = this.refs.send_statistics.getInput().checked;
            this.setState({
                sendStatistics: sendStatistics,
                personalizeStatistics: sendStatistics && this.refs.personalize_statistics.getInput().checked
            });
            this.validateContacts();
        },
        renderCheckbox: function(name, wrapperClassName) {
            return <controls.Input
                type='checkbox'
                ref={name}
                name={name}
                checked={name == 'personalize_statistics' ? this.state.personalizeStatistics : this.state.sendStatistics}
                label={$.t(this.ns + name)}
                wrapperClassName={wrapperClassName}
                disabled={name == 'personalize_statistics' && !this.state.sendStatistics}
                onChange={this.updateStates}
            />;
        },
        renderContactForm: function(labelClassName, wrapperClassName, hideErrors) {
            return _.map(['name', 'email', 'company'], function(name) {
                return (
                    <controls.Input
                        type='text'
                        key={name}
                        ref={name}
                        name={name}
                        label={$.t(this.ns + 'contacts.' + name)}
                        disabled={!this.state.personalizeStatistics}
                        inputClassName='input-xlarge'
                        labelClassName={labelClassName}
                        wrapperClassName={wrapperClassName}
                        onChange={this.validateContacts}
                        error={this.state.personalizeStatistics && _.contains(this.state.errors, name) ? hideErrors ? '' : $.t(this.ns + 'errors.' + name) : null}
                    />
                );
            }, this);
        }
    };
});
