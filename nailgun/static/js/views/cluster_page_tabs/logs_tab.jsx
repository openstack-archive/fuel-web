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
define(
[
    'react',
    'utils',
    'models',
    'jsx!component_mixins',
    'jsx!controls'
],
function(React, utils, models, componentMixins, controls) {
    'use strict';

    var LogsTab = React.createClass({
        mixins: [
            React.addons.LinkedStateMixin,
            React.BackboneMixin('model'),
            componentMixins.pollingMixin(5)
        ],
        shouldDataBeFetched: function() {
            var logsEntries = this.state.logsEntries,
                to = this.state.to;
            return to && logsEntries;
        },
        fetchData: function() {
            var request,
                logsEntries = this.state.logsEntries,
                to = this.state.to;
                request = this.fetchLogs({to: to})
                    .done(_.bind(function(data) {
                        this.setState({
                            logsEntries: _.union(data.entries, logsEntries),
                            to: data.to
                        });
                    }, this));
            return $.when(request);
        },
        getInitialState: function() {
            return {
                showMoreLogsLink: false,
                logsLoadingState: null,
                to: 0
            };
        },
        fetchLogs: function(data, callbacks) {
            var options = {
                url: '/api/logs',
                dataType: 'json',
                data: {
                    node: this.state.chosenNodeId,
                    source: this.state.chosenSourceId,
                    level: this.state.chosenLevelId
                },
                headers: {
                    'X-Auth-Token': app.keystoneClient.token
                }
            };
            _.extend(options, callbacks);
            _.extend(options.data, data);
            return $.ajax(options);
        },
        showLogs: function(params) {
            var options = this.getOptions();
            this.props.model.set({log_options: options}, {silent: true});
            app.navigate('#cluster/' + this.props.model.id + '/logs/' + utils.serializeTabOptions(options), {trigger: false, replace: true});
            this.fetchLogs(params)
                .done(_.bind(function(data) {
                    this.setState({
                        showMoreLogsLink: data.has_more || false,
                        logsEntries: data.entries,
                        logsLoadingState: 'done',
                        to: data.to
                    });
                    this.startPolling();
                }, this))
                .fail(_.bind(function() {
                    this.setState({
                        logsEntries: undefined,
                        logsLoadingState: 'fail'
                    });
                }, this));
        },
        getOptions: function() {
            var options = {};
            options.type = this.state.chosenType;
            if (options.type == 'remote') {
                options.node = this.state.chosenNodeId;
            }
            options.source = this.state.chosenSourceId;
            options.level = this.state.chosenLevelId.toLowerCase();
            return options;
        },
        onShowButtonClick: function(states) {
            this.setState(_.extend(states, {logsLoadingState: 'loading'}), _.bind(function() {
                this.showLogs({truncate_log: true});
            }, this));
        },
        onShowMoreClick: function(value) {
            if (value == 'all') {
                this.showLogs({});
            } else {
                var count = parseInt(value, 10) + this.state.logsEntries.length;
                this.showLogs({truncate_log: true, max_entries: count});
            }
        },
        render: function() {
            return (
                <div className='wrapper'>
                    <h3>{$.t('cluster_page.logs_tab.title')}</h3>
                    <div className='row'>
                        <LogFilterBar
                            cluster={this.props.model}
                            onShowButtonClick={this.onShowButtonClick} />
                    </div>
                    {this.state.logsLoadingState == 'fail' &&
                        <div className='logs-fetch-error alert alert-error'>{$.t('cluster_page.logs_tab.log_alert')}</div>
                    }
                    {this.state.logsEntries &&
                        <LogsTable
                            logsEntries={this.state.logsEntries}
                            showMoreLogsLink={this.state.showMoreLogsLink}
                            onShowMoreClick={this.onShowMoreClick} />
                    }
                    {this.state.logsLoadingState == 'loading' &&
                        <div className="logs-loading row row-fluid">
                            <controls.ProgressBar />
                        </div>
                    }
                </div>
            );
        }
    });

    var LogFilterBar = React.createClass({
        getInitialState: function() {
            return {
                chosenType: 'local',
                chosenNodeId: null,
                chosenSourceId: null,
                sourcesLoadingState: 'loading'
            };
        },
        fetchSources: function(type, nodeId) {
            var cluster = this.props.cluster,
                chosenNodeId = nodeId || cluster.get('nodes').first().id;
            this.sources = new models.LogSources();
            if (type == 'remote') {
                if (chosenNodeId) {
                    this.sources.deferred = this.sources.fetch({url: '/api/logs/sources/nodes/' + chosenNodeId});
                }
            } else if (!cluster.get('log_sources')) {
                this.sources.deferred = this.sources.fetch();
                this.sources.deferred.done(_.bind(function() {
                    cluster.set('log_sources', this.sources.toJSON());
                }, this));
            } else {
                this.sources.reset(cluster.get('log_sources'));
                this.sources.deferred = $.Deferred().resolve();
            }
            this.sources.deferred.done(_.bind(function() {
                var chosenSource = type == 'local' ? _.first(this.sources.reject({remote: true})) : this.sources.find({remote: true}),
                    chosenLevelId = chosenSource ? _.find(this.sources.get(chosenSource.id).get('levels')) : null;
                this.setState({
                    chosenType: type || this.state.chosenType,
                    sources: this.sources,
                    sourcesLoadingState: 'done',
                    chosenNodeId: chosenNodeId && type == 'remote' ? chosenNodeId : null,
                    chosenSourceId: chosenSource ? chosenSource.id : null,
                    chosenLevelId: chosenLevelId,
                    locked: false
                });
            }, this));
            this.sources.deferred.fail(_.bind(function() {
                this.setState({
                    chosenType: type || this.state.chosenType,
                    sources: {},
                    sourcesLoadingState: 'fail',
                    locked: false
                });
            }, this));
            return this.sources.deferred;
        },
        componentDidMount: function() {
            this.fetchSources(this.state.chosenType);
        },
        onTypeChange: function(name, value) {
            this.fetchSources(value);
        },
        onNodeChange: function(name, value) {
            this.fetchSources('remote', value);
        },
        onLevelChange: function(name, value) {
            this.setState({
                chosenLevelId: value,
                locked: false
            });
        },
        onSourceChange: function(name, value) {
            var levels = this.state.sources.get(value).get('levels');
            if (!_.contains(levels, this.state.chosenLevelId)) {
                this.setState({
                    chosenLevelId: _.first(levels),
                    chosenSourceId: value,
                    locked: false
                });
            } else {
                this.setState({
                    chosenSourceId: value,
                    locked: false
                });
            }
        },
        getLocalSources: function() {
            var sources = this.state.sources;
            if (sources && sources.length) {
                return sources.map(function(source) {
                    if (!source.get('remote')) {
                        return <option value={source.id} key={source.id}>{source.get('name')}</option>;
                    }
                }, this);
            }
            return sources;
        },
        getRemoteSources: function() {
            var options = {},
                groups = [''],
                sourcesByGroup = {'': []},
                sources = this.state.sources;
            if (sources.length) {
                sources.each(function(source) {
                    var group = source.get('group') || '';
                    if (!_.has(sourcesByGroup, group)) {
                        sourcesByGroup[group] = [];
                        groups.push(group);
                    }
                    sourcesByGroup[group].push(source);
                });
                _.each(groups, function(group) {
                    if (sourcesByGroup[group].length) {
                        options[group] = sourcesByGroup[group].map(function(source) {
                            return <option value={source.id} key={source.id}>{source.get('name')}</option>;
                        }, this);
                    }
                }, this);
            }
        },
        handleShowButtonClick: function() {
            this.setState({locked: true});
            this.props.onShowButtonClick({
                chosenType: this.state.chosenType,
                chosenNodeId: this.state.chosenNodeId,
                chosenSourceId: this.state.chosenSourceId,
                chosenLevelId: this.state.chosenLevelId
            });
        },
        render: function() {
            return (
                <div>
                    <div className='filter-bar'>
                        {this.renderTypeSelect()}
                        {this.state.chosenType == 'remote' && this.renderNodeSelect()}
                        {this.renderSourceSelect()}
                        {this.renderLevelSelect()}
                        <div className='filter-bar-item'>
                            <button
                                className='show-logs-btn btn'
                                onClick={this.handleShowButtonClick}
                                disabled={!this.state.chosenSourceId || this.state.locked ? 'disabled' : ''}>
                                {$.t('cluster_page.logs_tab.show')}
                            </button>
                        </div>
                    </div>
                    {this.state.sourcesLoadingState == 'fail' &&
                        <div className='node-sources-error alert alert-error'>{$.t('cluster_page.logs_tab.source_alert')}</div>
                    }
                </div>
            );
        },
        renderTypeSelect: function() {
            var types = [['local', 'Fuel Master']];
            if (this.props.cluster.get('nodes').length) {
                types.push(['remote', 'Other servers']);
            }
            var typeOptions = types.map(function(type, i) {
                return <option value={type[0]} key={type[0]} >{type[1]}</option>;
            });
            return <controls.Input
                    type='select'
                    labelClassName='filter-bar-label'
                    label={$.t('cluster_page.logs_tab.logs')}
                    wrapperClassName='filter-bar-item log-type-filter'
                    name='type'
                    className='filter-bar-dropdown input-medium'
                    onChange={this.onTypeChange}>
                    {typeOptions}</controls.Input>;
        },
        renderNodeSelect: function() {
            var nodeOptions = this.props.cluster.get('nodes').map(function(node) {
                    return <option value={node.id} key={node.id}>{node.get('name') || node.get('mac')}</option>;
                }, this);
            return <controls.Input
                    type='select'
                    labelClassName='filter-bar-label'
                    label={$.t('cluster_page.logs_tab.node')}
                    wrapperClassName='filter-bar-item log-node-filter'
                    name='node'
                    className='filter-bar-dropdown input-large'
                    onChange={this.onNodeChange}>
                    {nodeOptions}</controls.Input>;
        },
        renderSourceSelect: function() {
            var sourceOptions = {};
            if (this.state.chosenType == 'local') {
                sourceOptions = this.getLocalSources();
            } else {
                sourceOptions = this.getRemoteSources();
            }
            return <controls.Input
                    type='select'
                    labelClassName='filter-bar-label'
                    label={$.t('cluster_page.logs_tab.source')}
                    wrapperClassName='filter-bar-item log-source-filter'
                    name='source'
                    className='filter-bar-dropdown input-medium'
                    onChange={this.onSourceChange}
                    disabled={!this.state.chosenSourceId}>
                    {sourceOptions}</controls.Input>;
        },
        renderLevelSelect: function() {
            var levelOptions = {};
            if (this.state.chosenSourceId && this.state.sources.length) {
                levelOptions = this.state.sources.get(this.state.chosenSourceId).get('levels').map(function(level) {
                    return <option value={level} key={level}>{level}</option>;
                }, this);
            }
            return <controls.Input
                    type='select'
                    labelClassName='filter-bar-label'
                    label={$.t('cluster_page.logs_tab.min_level')}
                    wrapperClassName='filter-bar-item log-level-filter'
                    name='level'
                    className='filter-bar-dropdown input-medium'
                    onChange={this.onLevelChange}
                    disabled={!this.state.chosenLevelId}>
                    {levelOptions}</controls.Input>;
        }
    });

    var LogsTable = React.createClass({
        handleShowMoreClick: function(e) {this.props.onShowMoreClick($(e.target).text())},
        handleShowAllClick: function() {this.props.onShowMoreClick('all')},
        render: function() {
            var tabRows = [],
                logsEntries = this.props.logsEntries;
            if (logsEntries && logsEntries.length) {
                tabRows = logsEntries.map(function(entry, i) {
                    var key = logsEntries.length - i;
                    return <tr key={key} className={entry[1].toLowerCase()}>
                        <td className='nowrap'>{entry[0]}</td>
                        <td className='nowrap'>{entry[1]}</td>
                        <td><pre>{entry[2]}</pre></td>
                        </tr>;
                });
            }
            return (
                <table className='table enable-selection table-bordered table-condensed table-logs'>
                    <thead>
                        <tr>
                            <th>{$.t('cluster_page.logs_tab.date')}</th>
                            <th>{$.t('cluster_page.logs_tab.level')}</th>
                            <th>{$.t('cluster_page.logs_tab.message')}</th>
                        </tr>
                    </thead>
                    <tbody className='log-entries'>
                        {tabRows}
                    </tbody>
                    {this.props.showMoreLogsLink &&
                        <tfoot className={'entries-skipped-msg'}>
                            <tr>
                                <td colSpan='3'>
                                    <span>{$.t('cluster_page.logs_tab.bottom_text')}
                                    </span>: {[100, 500, 1000, 5000].map(function(count) {
                                        return <span className='show-more-entries' onClick={this.handleShowMoreClick} key={count}> {count} </span>;
                                    }, this)}
                                    <span className='show-all-entries' onClick={this.handleShowAllClick}>{$.t('cluster_page.logs_tab.all_logs')}</span>
                                </td>
                            </tr>
                        </tfoot>
                    }
                    {!logsEntries.length &&
                        <tfoot className='no-logs-msg'>
                            <tr>
                                <td colSpan='3' >{$.t('cluster_page.logs_tab.no_log_text')}</td>
                            </tr>
                        </tfoot>
                    }
                </table>
            );
        }
    });

    return LogsTab;
});
