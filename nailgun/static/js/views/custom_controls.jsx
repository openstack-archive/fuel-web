/*
 * Copyright 2014 Mirantis, Inc.
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
    'react',
    'utils',
    'jsx!views/controls'
], function($, _, React, utils, controls) {
    'use strict';

    var customControls = {};

    customControls.custom_repo_configuration = React.createClass({
        getInitialState: function() {
            return {labels: {MOS: 'Ubuntu repo', Fuel: 'Fuel repo'}};
        },
        validate: function(index) {
            var repo = this.props.value[index];
            if (repo.name && !$.trim(repo.name)) return {name: 'Empty name'};
            if (!repo.type) return null;
            if (repo.type != 'deb') return {repo: 'Invalid type'};
            if (!repo.uri || !repo.uri.match(utils.regexes.url)) return {repo: 'Invalid uri'};
            //if (repo.suite != 'deb') return 'Invalid suite';
            //if (repo.section != 'deb') return 'Invalid section';
            return null;
        },
        changeRepos: function(method, index, value) {
            var repos = _.cloneDeep(this.props.value);
            if (method == 'add') repos.push({type: '', name: '', uri: '', suite: '', section: '', priority: 1001});
            if (method == 'delete') repos.splice(index, 1);
            if (method == 'change_name') repos[index].name = value;
            if (method == 'change_repo') {
                value = $.trim(value).split(' ');
                var repo = repos[index];
                repo.type = value[0];
                repo.uri = value[1];
                repo.suite = value[2];
                repo.section = value[3];
            }
            this.props.settings.set('repo_setup.repos.value', repos);
        },
        checkReposAvailability: function() {
            return;
        },
        composeRepoValue: function(repo) {
            return [repo.type, repo.uri, repo.suite, repo.section].join(' ');
        },
        render: function() {
            if (this.props.cluster.get('release').get('operating_system') != 'Ubuntu') return null;
            var mainRepos = ['MOS', 'Fuel'];
            this.props.value.sort(function(a, b) {
                return _.indexOf(mainRepos, a) - _.indexOf(mainRepos, b);
            });
            return (
                <div className='table-wrapper repos'>
                    {this.props.value.map(function(repo, index) {
                        var error = this.validate(index);
                        if (_.contains(mainRepos, repo.name)) return <controls.Input
                            key={'repo-' + index}
                            type='text'
                            name={index}
                            defaultValue={this.composeRepoValue(repo)}
                            label={this.state.labels[repo.name]}
                            error={error && error.repo}
                            disabled={this.props.locked}
                            wrapperClassName='tablerow-wrapper'
                            onChange={this.changeRepos.bind(this, 'change')}
                        />;
                        return (
                            <div className='tablerow-wrapper repo-group' key={'repo-' + index}>
                                <controls.Input
                                    type='text'
                                    name={index}
                                    defaultValue={repo.name}
                                    error={error && error.name ? '' : null}
                                    disabled={this.props.locked}
                                    wrapperClassName='repo-name'
                                    onChange={this.changeRepos.bind(this, 'change_name')}
                                    placeholder='Repo name'
                                />
                                <controls.Input
                                    type='text'
                                    name={index}
                                    defaultValue={this.composeRepoValue(repo)}
                                    error={error && (error.repo || error.name)}
                                    disabled={this.props.locked}
                                    onChange={this.changeRepos.bind(this, 'change_repo')}
                                    deleteInput={this.changeRepos.bind(this, 'delete', index)}
                                />
                            </div>
                        );
                    }, this)}
                    <div className='buttons' key='buttons'>
                        <button key='addExtraRepo' className='btn btn-add-repo' onClick={this.changeRepos.bind(this, 'add')} disabled={this.props.locked}>
                            Add Extra Repo
                        </button>
                        <button key='checkRepos' className='btn btn-check-repos' onClick={this.checkReposAvailability} disabled={this.props.locked}>
                            Check Repos Availability
                        </button>
                    </div>
                </div>
            );
        }
    });

    return customControls;
});
