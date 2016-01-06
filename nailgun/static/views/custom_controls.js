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
    'views/controls'
], ($, _, i18n, React, utils, controls) => {
    'use strict';

    var customControls = {};

    customControls.custom_repo_configuration = React.createClass({
        statics: {
            // validate method represented as static method to support cluster settings validation
            validate: function(setting, models) {
                var ns = 'cluster_page.settings_tab.custom_repo_configuration.errors.',
                    nameRegexp = /^[\w-.]+$/,
                    os = models.release.get('operating_system');
                var errors = setting.value.map(function(repo) {
                    var error = {},
                        value = this.repoToString(repo, os);
                    if (!repo.name) {
                        error.name = i18n(ns + 'empty_name');
                    } else if (!repo.name.match(nameRegexp)) {
                        error.name = i18n(ns + 'invalid_name');
                    }
                    if (!value || !value.match(this.defaultProps.repoRegexes[os])) {
                        error.uri = i18n(ns + 'invalid_repo');
                    }
                    var priority = repo.priority;
                    if (_.isNaN(priority) || !_.isNull(priority) && (!(priority == _.parseInt(priority, 10)) || os == 'CentOS' && (priority < 1 || priority > 99))) {
                        error.priority = i18n(ns + 'invalid_priority');
                    }
                    return _.isEmpty(error) ? null : error;
                }, this);
                return _.compact(errors).length ? errors : null;
            },
            repoToString: function(repo, os) {
                var repoData = _.compact(this.defaultProps.repoAttributes[os].map((attribute) => repo[attribute]));
                if (!repoData.length) return ''; // in case of new repo
                return repoData.join(' ');
            }
        },
        getInitialState: function() {
            return {};
        },
        getDefaultProps: function() {
            return {
                repoRegexes: {
                    Ubuntu: /^(deb|deb-src)\s+(\w+:\/\/[\w\-.\/]+(?::\d+)?[\w\-.\/]+)\s+([\w\-.\/]+)(?:\s+([\w\-.\/\s]+))?$/i,
                    CentOS: /^(\w+:\/\/[\w\-.\/]+(?::\d+)?[\w\-.\/]+)\s*$/i
                },
                repoAttributes: {
                    Ubuntu: ['type', 'uri', 'suite', 'section'],
                    CentOS: ['uri']
                }
            };
        },
        changeRepos: function(method, index, value) {
            value = _.trim(value).replace(/\s+/g, ' ');
            var repos = _.cloneDeep(this.props.value),
                os = this.props.cluster.get('release').get('operating_system');
            switch (method) {
                case 'add':
                    var data = {
                        name: '',
                        type: '',
                        uri: '',
                        priority: this.props.extra_priority
                    };
                    if (os == 'Ubuntu') {
                        data.suite = '';
                        data.section = '';
                    } else {
                        data.type = 'rpm';
                    }
                    repos.push(data);
                    break;
                case 'delete':
                    repos.splice(index, 1);
                    this.setState({key: _.now()});
                    break;
                case 'change_name':
                    repos[index].name = value;
                    break;
                case 'change_priority':
                    repos[index].priority = value == '' ? null : Number(value);
                    break;
                default:
                    var repo = repos[index],
                        match = value.match(this.props.repoRegexes[os]);
                    if (match) {
                        _.each(this.props.repoAttributes[os], (attribute, index) => {
                            repo[attribute] = match[index + 1] || '';
                        });
                    } else {
                        repo.uri = value;
                    }
            }
            var path = this.props.settings.makePath(this.props.path, 'value');
            this.props.settings.set(path, repos);
            this.props.settings.isValid({models: this.props.configModels});
        },
        renderDeleteButton: function(index) {
            return (
                <button
                    className='btn btn-link'
                    onClick={this.changeRepos.bind(this, 'delete', index)}
                    disabled={this.props.disabled}
                >
                    <i className='glyphicon glyphicon-minus-sign' />
                </button>
            );
        },
        render: function() {
            var ns = 'cluster_page.settings_tab.custom_repo_configuration.',
                os = this.props.cluster.get('release').get('operating_system');
            return (
                <div className='repos' key={this.state.key}>
                    {this.props.description &&
                        <span className='help-block' dangerouslySetInnerHTML={{__html: utils.urlify(utils.linebreaks(_.escape(this.props.description)))}} />
                    }
                    {this.props.value.map(function(repo, index) {
                        var error = (this.props.error || {})[index],
                            props = {
                                name: index,
                                type: 'text',
                                disabled: this.props.disabled
                            };
                        return (
                            <div className='form-inline' key={'repo-' + index}>
                                <controls.Input
                                    {...props}
                                    defaultValue={repo.name}
                                    error={error && error.name}
                                    wrapperClassName='repo-name'
                                    onChange={this.changeRepos.bind(this, 'change_name')}
                                    label={index == 0 && i18n(ns + 'labels.name')}
                                    debounce
                                />
                                <controls.Input
                                    {...props}
                                    defaultValue={this.constructor.repoToString(repo, os)}
                                    error={error && (error.uri ? error.name ? '' : error.uri : null)}
                                    onChange={this.changeRepos.bind(this, null)}
                                    label={index == 0 && i18n(ns + 'labels.uri')}
                                    wrapperClassName='repo-uri'
                                    debounce
                                />
                                <controls.Input
                                    {...props}
                                    defaultValue={repo.priority}
                                    error={error && (error.priority ? (error.name || error.uri) ? '' : error.priority : null)}
                                    wrapperClassName='repo-priority'
                                    onChange={this.changeRepos.bind(this, 'change_priority')}
                                    extraContent={index > 0 && this.renderDeleteButton(index)}
                                    label={index == 0 && i18n(ns + 'labels.priority')}
                                    placeholder={i18n(ns + 'placeholders.priority')}
                                    debounce
                                />
                            </div>
                        );
                    }, this)}
                    <div className='buttons'>
                        <button key='addExtraRepo' className='btn btn-default btn-add-repo' onClick={this.changeRepos.bind(this, 'add')} disabled={this.props.disabled}>
                            {i18n(ns + 'add_repo_button')}
                        </button>
                    </div>
                </div>
            );
        }
    });

    return customControls;
});
