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
    'jquery',
    'underscore',
    'i18n',
    'react',
    'utils',
    'models',
    'jsx!component_mixins',
    'jsx!views/controls'
],
function($, _, i18n, React, utils, models, componentMixins, controls) {
    'use strict';

    var LogsTab = React.createClass({
        mixins: [
            componentMixins.pollingMixin(5)
        ],
        shouldDataBeFetched: function() {
            return this.state.to && this.state.logsEntries;
        },
        fetchData: function() {
            var request,
                logsEntries = this.state.logsEntries,
                from = this.state.from,
                to = this.state.to;
            request = this.fetchLogs({from: from, to: to})
                .done(_.bind(function(data) {
                    this.setState({
                        logsEntries: data.entries.concat(logsEntries),
                        from: data.from,
                        to: data.to
                    });
                }, this));
            return $.when(request);
        },
        getInitialState: function() {
            return {
                showMoreLogsLink: false,
                loading: null,
                from: -1,
                to: 0
            };
        },
        fetchLogs: function(data, callbacks) {
            var options = {
                url: '/api/logs',
                dataType: 'json',
                data: {
                    node: this.state.selectedNodeId,
                    source: this.state.selectedSourceId,
                    level: this.state.selectedLevelId
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
            params = params || {};
            var options = this.composeOptions();
            this.stopPolling();
            this.props.cluster.set({log_options: options}, {silent: true});
            app.navigate('#cluster/' + this.props.cluster.id + '/logs/' + utils.serializeTabOptions(options), {trigger: false, replace: true});
            this.fetchLogs(params)
                .done(_.bind(function(data) {
                    var logsEntries = this.state.logsEntries || [];

                    this.setState({
                        showMoreLogsLink: data.has_more || false,
                        logsEntries: params.fetch_older ? logsEntries.concat(data.entries) : data.entries,
                        loading: 'done',
                        from: data.from,
                        to: data.to
                    });
                    this.startPolling();
                }, this))
                .fail(_.bind(function() {
                    this.setState({
                        logsEntries: undefined,
                        loading: 'fail'
                    });
                }, this));
        },
        composeOptions: function() {
            var options = {
                type: this.state.selectedType,
                source: this.state.selectedSourceId,
                level: this.state.selectedLevelId ? this.state.selectedLevelId.toLowerCase() : null
            };
            if (options.type == 'remote') options.node = this.state.selectedNodeId;
            return options;
        },
        onShowButtonClick: function(states) {
            this.setState(_.extend(states, {loading: 'loading'}), _.bind(function() {
                this.showLogs();
            }, this));
        },
        onShowMoreClick: function(value) {
            var options = {
                max_entries: value,
                fetch_older: true,
                from: this.state.from
            };
            this.showLogs(options);
        },
        render: function() {
            return (
                <div className='row'>
                    <div className='title'>{i18n('cluster_page.logs_tab.title')}</div>
                    <div className='col-xs-12 content-elements'>
                        <LogFilterBar
                            cluster={this.props.cluster}
                            tabOptions={this.props.tabOptions}
                            onShowButtonClick={this.onShowButtonClick} />
                        {this.state.loading == 'fail' &&
                            <div className='logs-fetch-error alert alert-danger'>
                                {i18n('cluster_page.logs_tab.log_alert')}
                            </div>
                        }
                        {this.state.loading == 'loading' && <controls.ProgressBar />}
                        {this.state.logsEntries &&
                            <LogsTable
                                logsEntries={this.state.logsEntries}
                                showMoreLogsLink={this.state.showMoreLogsLink}
                                onShowMoreClick={this.onShowMoreClick} />
                        }
                    </div>
                </div>
            );
        }
    });

    var LogFilterBar = React.createClass({
        getInitialState: function() {
            // FIXME(vkramskikh): we need to get rid of log_options - there
            // should be single source of truth: tabOptions/URL parameters
            var options = this.props.tabOptions[0] ? utils.deserializeTabOptions(_.compact(this.props.tabOptions).join('/')) : this.props.cluster.get('log_options') || {};
            return {
                chosenType: options.type || 'local',
                chosenNodeId: options.node || null,
                chosenSourceId: options.source || null,
                chosenLevelId: options.level ? options.level.toUpperCase() : 'INFO',
                sourcesLoadingState: 'loading',
                sources: [],
                locked: false
            };
        },
        fetchSources: function(type, nodeId) {
            var cluster = this.props.cluster,
                nodes = cluster.get('nodes'),
                chosenNodeId = nodeId || (nodes.length ? nodes.first().id : null);
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
                var filteredSources = this.sources.filter(function(source) {return source.get('remote') == (type != 'local');}),
                    chosenSource = _.findWhere(filteredSources, {id: this.state.chosenSourceId}) || _.first(filteredSources),
                    chosenLevelId = chosenSource ? _.contains(chosenSource.get('levels'), this.state.chosenLevelId) ? this.state.chosenLevelId : _.first(chosenSource.get('levels')) : null;
                this.setState({
                    chosenType: type,
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
                    chosenType: type,
                    sources: {},
                    sourcesLoadingState: 'fail',
                    locked: false
                });
            }, this));
            return this.sources.deferred;
        },
        componentDidMount: function() {
            this.fetchSources(this.state.chosenType, this.state.chosenNodeId)
                .done(this.handleShowButtonClick);
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
            var levels = this.state.sources.get(value).get('levels'),
                data = {locked: false, chosenSourceId: value};
            if (!_.contains(levels, this.state.chosenLevelId)) data.chosenLevelId = _.first(levels);
            this.setState(data);
        },
        getLocalSources: function() {
            return this.state.sources.map(function(source) {
                if (!source.get('remote')) {
                    return <option value={source.id} key={source.id}>{source.get('name')}</option>;
                }
            }, this);
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
                        var option = sourcesByGroup[group].map(function(source) {
                            return <option value={source.id} key={source.id}>{source.get('name')}</option>;
                        }, this);
                        options[group] = group ? <optgroup label={group}>{option}</optgroup> : option;
                    }
                }, this);
            }
            return options;
        },
        handleShowButtonClick: function() {
            this.setState({locked: true});
            this.props.onShowButtonClick({
                selectedType: this.state.chosenType,
                selectedNodeId: this.state.chosenNodeId,
                selectedSourceId: this.state.chosenSourceId,
                selectedLevelId: this.state.chosenLevelId
            });
        },
        render: function() {
            var isRemote = this.state.chosenType == 'remote';
            return (
                <div className='well well-sm'>
                    <div className='sticker row'>
                        {this.renderTypeSelect()}
                        {isRemote && this.renderNodeSelect()}
                        {this.renderSourceSelect()}
                        {this.renderLevelSelect()}
                        {this.renderFilterButton(isRemote)}
                    </div>
                    {this.state.sourcesLoadingState == 'fail' &&
                        <div className='node-sources-error alert alert-danger'>
                            {i18n('cluster_page.logs_tab.source_alert')}
                        </div>
                    }
                </div>
            );
        },
        renderFilterButton: function(isRemote) {
            return <div className={utils.classNames({
                'form-group': true,
                'col-md-4 col-sm-12': isRemote,
                'col-md-6 col-sm-3': !isRemote
            })}>
                <label />
                <button
                    className='btn btn-default pull-right'
                    onClick={this.handleShowButtonClick}
                    disabled={!this.state.chosenSourceId || this.state.locked}
                >
                    {i18n('cluster_page.logs_tab.show')}
                </button>
            </div>;
        },
        renderTypeSelect: function() {
            var types = [['local', 'Fuel Master']];
            if (this.props.cluster.get('nodes').length) {
                types.push(['remote', 'Other servers']);
            }
            var typeOptions = types.map(function(type) {
                return <option value={type[0]} key={type[0]}>{type[1]}</option>;
            });
            return <div className='col-md-2 col-sm-3'>
                <controls.Input
                    type='select'
                    label={i18n('cluster_page.logs_tab.logs')}
                    value={this.state.chosenType}
                    wrapperClassName='filter-bar-item log-type-filter'
                    name='type'
                    onChange={this.onTypeChange}
                    children={typeOptions}
                />
            </div>;
        },
        renderNodeSelect: function() {
            var nodeOptions = this.props.cluster.get('nodes').map(function(node) {
                    return <option value={node.id} key={node.id}>{node.get('name') || node.get('mac')}</option>;
                }, this);
            return <div className='col-md-2 col-sm-3'>
                <controls.Input
                    type='select'
                    label={i18n('cluster_page.logs_tab.node')}
                    value={this.state.chosenNodeId}
                    wrapperClassName='filter-bar-item log-node-filter'
                    name='node'
                    onChange={this.onNodeChange}
                    children={nodeOptions}
                />
            </div>;
        },
        renderSourceSelect: function() {
            var sourceOptions = this.state.chosenType == 'local' ? this.getLocalSources() : this.getRemoteSources();
            return <div className='col-md-2 col-sm-3'>
                <controls.Input
                    type='select'
                    label={i18n('cluster_page.logs_tab.source')}
                    value={this.state.chosenSourceId}
                    wrapperClassName='filter-bar-item log-source-filter'
                    name='source'
                    onChange={this.onSourceChange}
                    disabled={!this.state.chosenSourceId}
                    children={sourceOptions}
                />
            </div>;
        },
        renderLevelSelect: function() {
            var levelOptions = {};
            if (this.state.chosenSourceId && this.state.sources.length) {
                levelOptions = this.state.sources.get(this.state.chosenSourceId).get('levels').map(function(level) {
                    return <option value={level} key={level}>{level}</option>;
                }, this);
            }
            return <div className='col-md-2 col-sm-3'>
                <controls.Input
                    type='select'
                    label={i18n('cluster_page.logs_tab.min_level')}
                    value={this.state.chosenLevelId}
                    wrapperClassName='filter-bar-item log-level-filter'
                    name='level'
                    onChange={this.onLevelChange}
                    disabled={!this.state.chosenLevelId}
                    children={levelOptions}
                />
            </div>;
        }
    });

    var LogsTable = React.createClass({
        handleShowMoreClick: function(value) { return this.props.onShowMoreClick(value); },
        getLevelClass: function(level) {
            return {
                DEBUG: '',
                INFO: 'text-info',
                WARNING: 'text-warning',
                ERROR: 'text-danger',
                CRITICAL: 'text-critical'
            }[level];
        },
        render: function() {
            var tabRows = [],
                logsEntries = this.props.logsEntries;
            if (logsEntries && logsEntries.length) {
                tabRows = _.map(
                    logsEntries,
                    function(entry, index) {
                        var key = logsEntries.length - index;
                        return <tr key={key} className={this.getLevelClass(entry[1])}>
                            <td>{entry[0]}</td>
                            <td>{entry[1]}</td>
                            <td>{entry[2]}</td>
                        </tr>;
                    },
                    this
                );
            }
            return logsEntries.length ?
                <table className='table log-entries'>
                    <thead>
                        <tr>
                            <th className='col-date'>{i18n('cluster_page.logs_tab.date')}</th>
                            <th className='col-level'>{i18n('cluster_page.logs_tab.level')}</th>
                            <th className='col-message'>{i18n('cluster_page.logs_tab.message')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {tabRows}
                    </tbody>
                    {this.props.showMoreLogsLink &&
                        <tfoot className='entries-skipped-msg'>
                            <tr>
                                <td colSpan='3' className='text-center'>
                                    <span>{i18n('cluster_page.logs_tab.bottom_text')}</span>:
                                    {
                                        [100, 500, 1000, 5000].map(
                                            function(count) {
                                                return <button className='btn btn-link show-more-entries' onClick={_.bind(this.handleShowMoreClick, this, count)} key={count}>{count} </button>;
                                            },
                                            this
                                        )
                                    }
                                </td>
                            </tr>
                        </tfoot>
                    }
                </table>
                :
                <div className='no-logs-msg'>{i18n('cluster_page.logs_tab.no_log_text')}</div>;
        }
    });

    return LogsTab;
});
