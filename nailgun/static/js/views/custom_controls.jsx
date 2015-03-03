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
    'jsx!views/controls'
], function($, _, i18n, React, controls) {
    'use strict';

    var customControls = {};

    var repoRegexp = /^(deb|deb-src)\s+(\w+:\/\/[\w\-.\/]+(?::\d+)?[\w\-.\/]+)\s+([\w\-.\/]+)(?:\s+([\w\-.\/]+))?$/i,
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
                        error.repo = i18n(ns + 'invalid_repo');
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
            value = $.trim(value);
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
            var mainRepos = ['MOS', 'Fuel'];
            this.props.value.sort(function(a, b) {
                return _.indexOf(mainRepos, a) - _.indexOf(mainRepos, b);
            });

            var ns = 'cluster_page.settings_tab.custom_repo_configuration.';
            return (
                <div className='table-wrapper repos' key={this.state.key}>
                    {this.props.value.map(function(repo, index) {
                        var error = (this.props.error || {})[index],
                            props = {
                                name: index,
                                type: 'text',
                                disabled: this.props.disabled,
                                defaultValue: repoToString(repo),
                                onChange: this.changeRepos.bind(this, null)
                            };
                        if (_.contains(mainRepos, repo.name)) {
                            return <controls.Input
                                {...props}
                                key={'repo-' + index}
                                label={i18n(ns + 'repo_labels.' + repo.name)}
                                error={error && error.repo}
                                wrapperClassName='tablerow-wrapper'
                            />;
                        }
                        return (
                            <div className='tablerow-wrapper repo-group' key={'repo-' + index}>
                                <controls.Input
                                    {...props}
                                    defaultValue={repo.name}
                                    error={error && error.name}
                                    wrapperClassName='repo-name'
                                    onChange={this.changeRepos.bind(this, 'change_name')}
                                    placeholder={i18n(ns + 'repo_name_placeholder')}
                                />
                                <controls.Input
                                    {...props}
                                    error={error && (error.name ? null : error.repo)}
                                    extraContent={this.renderDeleteButton(index)}
                                />
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
