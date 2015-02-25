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

    customControls.custom_repo_configuration = React.createClass({
        getInitialState: function() {
            return {
                ns: 'cluster_page.settings_tab.custom_repo_configuration.',
                regexes: {
                    name: /^[\w-]+$/,
                    repo: /^(deb|deb-src)\s+(([A-z0-9]+:\/\/[\w-.\/]+)(:[0-9]+)?([\w-.\/]+))\s+([\w-.\/]+)\s+([\w-.\/\s]+)$/
                }
            };
        },
        validate: function() {
            return this.props.value.map(function(repo) {
                var error = {},
                    value = this.getRepoValue(repo),
                    ns = this.state.ns + 'errors.';
                if (!repo.name) {
                    error.name = i18n(ns + 'empty_name');
                } else if (!repo.name.match(this.state.regexes.name)) {
                    error.name = i18n(ns + 'invalid_name');
                }
                if (!value || !value.match(this.state.regexes.repo)) {
                    error.repo = i18n(ns + 'invalid_repo');
                }
                return _.isEmpty(error) ? null : error;
            }, this);
        },
        changeRepos: function(method, index, value) {
            var repos = _.cloneDeep(this.props.value);
            switch (method) {
                case 'add':
                    repos.push({name: '', type: '', uri: '', suite: '', section: '', priority: this.props.metadata.extra_priority});
                    break;
                case 'delete':
                    repos.splice(index, 1);
                    this.setState({key: Date.now()});
                    break;
                case 'change_name':
                    repos[index].name = $.trim(value);
                    break;
                default:
                    var repo = repos[index],
                        match = value.match(this.state.regexes.repo);
                    if (match) {
                        repo.type = match[1];
                        repo.uri = match[2];
                        repo.suite = match[6];
                        repo.section = match[7];
                    } else {
                        repo.type = value;
                    }
            }
            var path = this.props.settings.makePath(this.props.path, 'value');
            this.props.settings.set(path, repos);
            this.props.settings.isValid({models: this.props.configModels});
        },
        getRepoValue: function(repo) {
            return $.trim([repo.type, repo.uri, repo.suite, repo.section].join(' '));
        },
        renderDeleteButton: function(index) {
            return (
                <button
                    className='btn btn-link btn-delete-input'
                    onClick={this.changeRepos.bind(this, 'delete', index)}
                    disabled={this.props.locked}
                >
                    <i className='icon-minus-circle' />
                </button>
            );
        },
        render: function() {
            if (this.props.cluster.get('release').get('operating_system') != 'Ubuntu') return null;

            var mainRepos = ['MOS', 'Fuel'];
            this.props.value.sort(function(a, b) {
                return _.indexOf(mainRepos, a) - _.indexOf(mainRepos, b);
            });

            var errors = this.validate();
            return (
                <div className='table-wrapper repos' key={this.state.key}>
                    {this.props.value.map(function(repo, index) {
                        var error = errors[index],
                            props = {
                                name: index,
                                type: 'text',
                                disabled: this.props.locked,
                                defaultValue: this.getRepoValue(repo),
                                onChange: this.changeRepos.bind(this, null)
                            };
                        if (_.contains(mainRepos, repo.name)) {
                            return <controls.Input
                                {...props}
                                key={'repo-' + index}
                                label={i18n(this.state.ns + 'repo_labels.' + repo.name)}
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
                                    placeholder={i18n(this.state.ns + 'repo_name_placeholder')}
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
                        <button key='addExtraRepo' className='btn' onClick={this.changeRepos.bind(this, 'add')} disabled={this.props.locked}>
                            {i18n(this.state.ns + 'add_repo_button')}
                        </button>
                    </div>
                </div>
            );
        }
    });

    return customControls;
});
