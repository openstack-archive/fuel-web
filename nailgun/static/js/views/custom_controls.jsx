/*
 * Copyright 2015 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the 'License'); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
**/

define([
    'jquery',
    'underscore',
    'i18n',
    'react',
    'utils',
    'jsx!views/controls'
], function($, _, i18n, React, utils, controls) {
    'use strict';

    var customControls = {};

    var repoRegexp = /^(deb|deb-src)\s+(\w+:\/\/[\w\-.\/]+(?::\d+)?[\w\-.\/]+)\s+([\w\-.\/]+)(?:\s+([\w\-.\/\s]+))?$/i,
        repoAttributes = ['type', 'uri', 'suite', 'section'],
        repoToString = function(repo) {
            var repoData = _.compact(repoAttributes.map(function(attribute) {return repo[attribute];}));
            if (!repoData.length) return ''; // in case of new repo
            return repoData.join(' ');
        };

    customControls.custom_repo_configuration = React.createClass({
        statics: {
            validate: function(setting) {
                var ns = 'cluster_page.settings_tab.custom_repo_configuration.errors.',
                    nameRegexp = /^[\w-]+$/;
                var errors = setting.value.map(function(repo) {
                    var error = {},
                        value = repoToString(repo);
                    if (!repo.name) {
                        error.name = i18n(ns + 'empty_name');
                    } else if (!repo.name.match(nameRegexp)) {
                        error.name = i18n(ns + 'invalid_name');
                    }
                    if (!value || !value.match(repoRegexp)) {
                        error.uri = i18n(ns + 'invalid_repo');
                    }
                    if (_.isNaN(repo.priority) || !(_.isNumber(repo.priority) || _.isNull(repo.priority))) {
                        error.priority = i18n(ns + 'invalid_priority');
                    }
                    return _.isEmpty(error) ? null : error;
                }, this);
                return _.compact(errors).length ? errors : null;
            }
        },
        getInitialState: function() {
            return {};
        },
        changeRepos: function(method, index, value) {
            value = $.trim(value).replace(/\s+/g, ' ');
            var repos = _.cloneDeep(this.props.value);
            switch (method) {
                case 'add':
                    repos.push({
                        name: '',
                        type: '',
                        uri: '',
                        suite: '',
                        section: '',
                        priority: this.props.extra_priority
                    });
                    break;
                case 'delete':
                    repos.splice(index, 1);
                    this.setState({key: _.now()});
                    break;
                case 'change_name':
                    repos[index].name = value;
                    break;
                case 'change_priority':
                    repos[index].priority = value == '' ? null : parseInt(value, 10);
                    break;
                default:
                    var repo = repos[index],
                        match = value.match(repoRegexp);
                    if (match) {
                        _.each(repoAttributes, function(attribute, index) {
                            repo[attribute] = match[index + 1] || '';
                        });
                    } else {
                        repo.type = value;
                    }
            }
            var path = this.props.settings.makePath(this.props.path, 'value');
            this.props.settings.set(path, repos);
            this.props.settings.isValid({models: this.props.configModels});
        },
        renderDeleteButton: function(index) {
            return (
                <button
                    className='btn btn-link btn-delete-input'
                    onClick={this.changeRepos.bind(this, 'delete', index)}
                    disabled={this.props.disabled}
                >
                    <i className='icon-minus-circle' />
                </button>
            );
        },
        render: function() {
            var ns = 'cluster_page.settings_tab.custom_repo_configuration.',
                isExperimental = _.contains(app.version.get('feature_groups'), 'experimental'),
                classes = {
                    'table-wrapper repos': true,
                    experimental: isExperimental
                };

            return (
                <div className={utils.classNames(classes)} key={this.state.key}>
                    {this.props.description &&
                        <div className='custom-description parameter-description'>
                            {this.props.description}
                        </div>
                    }
                    {this.props.value.map(function(repo, index) {
                        var error = (this.props.error || {})[index],
                            props = {
                                name: index,
                                type: 'text',
                                disabled: this.props.disabled
                            };
                        return (
                            <div className='tablerow-wrapper repo-group' key={'repo-' + index}>
                                <controls.Input
                                    {...props}
                                    defaultValue={repo.name}
                                    error={error && error.name}
                                    wrapperClassName='repo-name'
                                    onChange={this.changeRepos.bind(this, 'change_name')}
                                    label={index == 0 && i18n(ns + 'labels.name')}
                                />
                                <controls.Input
                                    {...props}
                                    defaultValue={repoToString(repo)}
                                    error={error && (error.uri ? error.name ? '' : error.uri : null)}
                                    onChange={this.changeRepos.bind(this, null)}
                                    extraContent={!isExperimental && index > 0 && this.renderDeleteButton(index)}
                                    label={index == 0 && i18n(ns + 'labels.uri')}
                                />
                                {isExperimental &&
                                    <controls.Input
                                        {...props}
                                        defaultValue={repo.priority}
                                        error={error && (error.priority ? (error.name || error.uri) ? '' : error.priority : null)}
                                        wrapperClassName='repo-priority'
                                        onChange={this.changeRepos.bind(this, 'change_priority')}
                                        extraContent={index > 0 && this.renderDeleteButton(index)}
                                        label={index == 0 && i18n(ns + 'labels.priority')}
                                        placeholder={i18n(ns + 'placeholders.priority')}
                                    />
                                }
                            </div>
                        );
                    }, this)}
                    <div className='buttons' key='buttons'>
                        <button key='addExtraRepo' className='btn' onClick={this.changeRepos.bind(this, 'add')} disabled={this.props.disabled}>
                            {i18n(ns + 'add_repo_button')}
                        </button>
                    </div>
                </div>
            );
        }
    });

    return customControls;
});
