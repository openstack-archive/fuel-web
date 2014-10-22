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
define([
    'jquery',
    'underscore',
    'react',
    'utils',
    'models',
    'jsx!views/controls'
], function($, _, React, utils, models, controls) {
    'use strict';

    return {
        propTypes: {
            settings: React.PropTypes.object.isRequired
        },
        saveSettings: function(e) {
            e.preventDefault();
            this.props.settings.isValid({models: {master_node_settings: this.props.settings}});
            if (this.props.settings.validationError) {
                this.forceUpdate();
                return (new $.Deferred()).reject();
            }
            this.setState({actionInProgress: true});
            return this.props.settings.save(null, {patch: true, wait: true, validate: false})
                .always(_.bind(function() {
                    this.setState({actionInProgress: false});
                }, this))
                .fail(function() {
                    utils.showErrorDialog({
                        title: $.t('welcome_page.error_title'),
                        message: $.t('welcome_page.error_warning')
                    });
                });
        },
        onSettingChange: function(name, value) {
            this.props.settings.set(name + '.value', value);
            this.props.settings.isValid({models: {master_node_settings: this.props.settings}});
        },
        checkRestrictions: function(name) {
            return this.props.settings.checkRestrictions({master_node_settings: this.props.settings}, 'disable', name);
        },
        get: function() {
            return this.props.settings.get(utils.makePath.apply(utils, arguments));
        },
        renderInput: function(setting, groupName, settingName, labelClassName, wrapperClassName, hideErrors) {
            var name = utils.makePath(groupName, settingName),
                error = this.props.settings.validationError,
                disabled = this.checkRestrictions(utils.makePath(groupName, 'metadata')) || this.checkRestrictions(name);
            return (
                <controls.Input
                    key={name}
                    type={setting.type}
                    name={name}
                    label={setting.label}
                    checked={!disabled && setting.value}
                    value={setting.value}
                    disabled={disabled}
                    inputClassName={setting.type == 'text' && 'input-xlarge'}
                    labelClassName={labelClassName}
                    wrapperClassName={wrapperClassName}
                    onChange={this.onSettingChange}
                    error={(error && error[name]) ? hideErrors ? '' : error[name] : null}
                />
            );
        }
    };
});
