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
        fetchData: function() {
            var request,
                logsEntries = this.state.logsEntries,
                to = this.state.to;
            if (to && logsEntries && this.state.locked) {
                request = this.fetchLogs({to: to})
                    .done(_.bind(function(data) {
                        this.setState({
                            logsEntries: _.union(data.entries, logsEntries),
                            to: data.to
                        });
                    }, this));
                }
            return $.when(request);
        },
        getInitialState: function() {
            return {
                chosenType: 'local',
                chosenNode: null,
                chosenSource: null,
                logsHasMore: false,
                logsLoadingState: undefined,
                sourcesLoadingState: undefined,
                to: 0
            };
        },
        fetchSources: function(type, nodeId) {
            var cluster = this.props.model,
                chosenNode = nodeId ? nodeId : _.first(this.props.model.get('nodes').models);
            this.sources = new models.LogSources();
            if (type == 'remote' && chosenNode) {
                this.sources.deferred = this.sources.fetch({url: '/api/logs/sources/nodes/' + chosenNode.id});
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
                var chosenSourceId = null,
                    chosenLevelId = null;
                if (this.sources.length) {
                    if (type == 'local') {
                        chosenSourceId = this.sources.find({remote: undefined}).id;
                    } else {
                        chosenSourceId = this.sources.find({remote: true}).id;
                    }
                    chosenLevelId = _.find(this.sources.get(chosenSourceId).get('levels'));
                }
                this.setState({
                    sourcesLoadingState: 'done',
                    chosenNode: chosenNode && (type == 'remote') ? chosenNode.id : null,
                    chosenSource: chosenSourceId,
                    chosenLevel: chosenLevelId,
                    locked: false
                });
            }, this));
            this.sources.deferred.fail(_.bind(function() {
                this.setState({
                    sourcesLoadingState: 'fail',
                    locked: false
                });
            }, this));
            return this.sources.deferred;
        },
        componentDidMount: function() {
            this.fetchSources(this.state.chosenType);
        },
        fetchLogs: function(data, callbacks) {
            var options = {
                url: '/api/logs',
                dataType: 'json',
                data: {
                    node: this.state.chosenNode,
                    source: this.state.chosenSource,
                    level: this.state.chosenLevel
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

            this.setState({logsLoadingState: 'loading'});
            this.props.model.set({'log_options': options}, {silent: true});
            app.navigate('#cluster/' + this.props.model.id + '/logs/' + utils.serializeTabOptions(options), {trigger: false, replace: true});

            this.fetchLogs(params)
                .done(_.bind(function(data) {
                    this.setState({
                        logsHasMore: data.has_more || false,
                        logsEntries: data.entries,
                        locked: true,
                        logsLoadingState: 'done',
                        to: data.to
                    });
                }, this))
                .fail(_.bind(function() {
                    this.setState({
                        logsEntries: undefined,
                        locked: false,
                        logsLoadingState: 'fail'
                    });
                }, this));
        },
        getOptions: function() {
            var options = {};
            options.type = this.state.chosenType;
            if (options.type == 'remote') {
                options.node = this.state.chosenNode;
            }
            options.source = this.state.chosenSource;
            options.level = this.state.chosenLevel.toLowerCase();
            return options;
        },
        handleTypeUpdate: function(value) {
            this.setState({chosenType: value});
            this.fetchSources(value);
        },
        handleNodeUpdate: function(value) {
            this.fetchSources('remote', value);
        },
        handleSourceUpdate: function(value) {
            this.setState({
                chosenSource: value,
                locked: false
            })},
        handleLevelUpdate: function(value) {
            this.setState({
                chosenLevel: value,
                locked: false
            })},
        onShowButtonClick: function() {
            this.showLogs({truncate_log: true});
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
            var sources = this.sources;
            return (
                <div className='wrapper'>
                    <h3>{$.t('cluster_page.logs_tab.title')}</h3>
                    <div className='row'>
                        <div className='filter-bar'>
                            <SelectWrapper
                                cluster={this.props.model}
                                updateType={this.handleTypeUpdate}
                                updateNode={this.handleNodeUpdate}
                                updateSource={this.handleSourceUpdate}
                                updateLevel={this.handleLevelUpdate}
                                chosenType={this.state.chosenType}
                                chosenSource={this.state.chosenSource}
                                chosenLevel={this.state.chosenLevel}
                                sources={sources} />
                            <div className='filter-bar-item'>
                                 <button
                                    className='show-logs-btn btn'
                                    onClick={this.onShowButtonClick}
                                    disabled={!this.state.chosenSource || this.state.locked ? 'disabled' : ''}>
                                    {$.t('cluster_page.logs_tab.show')}
                                </button>
                            </div>
                        </div>
                    </div>
                    {(this.state.logsLoadingState == 'fail') &&
                        <div className='logs-fetch-error alert alert-error'>{$.t('cluster_page.logs_tab.log_alert')}</div>
                    }
                    {(this.state.sourcesLoadingState == 'fail') &&
                        <div className='node-sources-error alert alert-error'>{$.t('cluster_page.logs_tab.source_alert')}</div>
                    }
                    {this.state.logsEntries &&
                        <LogsTable
                            logsEntries={this.state.logsEntries}
                            logsHasMore={this.state.logsHasMore}
                            onShowMoreClick={this.onShowMoreClick} />
                    }
                    {(this.state.logsLoadingState == 'loading') &&
                        <div className="logs-loading row row-fluid">
                            <controls.ProgressBar />
                        </div>
                    }
                </div>
            );
        }
    })

    var SelectWrapper = React.createClass({
        onTypeChange: function(e) {this.props.updateType(e.target.value)},
        onNodeChange: function(e) {this.props.updateNode(e.target.value)},
        onLevelChange: function(e) {this.props.updateLevel(e.target.value)},
        onSourceChange: function(e) {
            this.props.updateSource(e.target.value);
            var levels = this.props.sources.get(e.target.value).get('levels');
            if (!_.contains(levels, this.props.chosenLevel)) {
                this.props.updateLevel(_.first(levels))
            }
        },
        getLocalSources: function() {
            var options = {},
                sources = this.props.sources;
            if (sources && sources.length) {
                options = sources.map(function(source){
                    if (!source.get('remote')) {
                        return <option value={source.id} key={source.id}>{source.get('name')}</option>;
                    }
                }, this);
            }
            return options;
        },
        getRemoteSources: function() {
            var options = {},
                groups = [''],
                sourcesByGroup = {'': []},
                sources = this.props.sources;
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
                        options[group] = sourcesByGroup[group].map(function(source){
                            return <option value={source.id} key={source.id}>{source.get('name')}</option>;
                        }, this);
                    }
                }, this);
            }
        },
        render: function() {
            return (
                <div>
                    {this.renderTypeSelect()}
                    {(this.props.chosenType != 'local') && this.renderNodeSelect()}
                    {this.renderSourceSelect()}
                    {this.renderLevelSelect()}
                </div>
            );
        },
        renderTypeSelect: function() {
            var types = [['local', 'Fuel Master']];
            if (this.props.cluster.get('nodes').length) {
                types.push(['remote', 'Other servers']);
            }
            var typeOptions = types.map(function(type, i){
                return <option value={type[0]} key={type[0]} >{type[1]}</option>;
            });
            return (
                <div className='filter-bar-item log-type-filter'>
                    <div className='filter-bar-label'>{$.t('cluster_page.logs_tab.logs')}</div>
                    <select name='type' onChange={this.onTypeChange} className='filter-bar-dropdown input-medium'>
                        {typeOptions}
                    </select>
                </div>
            );
        },
        renderNodeSelect: function() {
            var nodeOptions = this.props.cluster.get('nodes').map(function(node){
                    return <option value={node.id} key={node.id}>{node.get('name') || node.get('mac')}</option>;
                }, this);
            return (
                <div className='filter-bar-item log-node-filter'>
                    <div className='filter-bar-label'>{$.t('cluster_page.logs_tab.node')}</div>
                    <select name='node' onChange={this.onNodeChange} className='filter-bar-dropdown input-large'>
                        {nodeOptions}
                    </select>
                </div>
            );
        },
        renderSourceSelect: function() {
            var sourceOptions = {};
            if (this.props.chosenType == 'local') {sourceOptions = this.getLocalSources();}
            else {sourceOptions = this.getRemoteSources();}
            return (
                <div className='filter-bar-item log-source-filter'>
                    <div className='filter-bar-label'>{$.t('cluster_page.logs_tab.source')}</div>
                    <select name='source' onChange={this.onSourceChange} className='filter-bar-dropdown input-medium'>
                        {sourceOptions}
                    </select>
                </div>
            );
        },
        renderLevelSelect: function() {
            var levelOptions = {};
            if (this.props.chosenSource && this.props.sources.length) {
                levelOptions = this.props.sources.get(this.props.chosenSource).get('levels').map(function(level){
                    return <option value={level} key={level}>{level}</option>;
                }, this);
            }
            return (
                <div className='filter-bar-item log-level-filter'>
                    <div className='filter-bar-label'>{$.t('cluster_page.logs_tab.level')}</div>
                    <select name='level' ref='levelSelect' onChange={this.onLevelChange} className='filter-bar-dropdown input-medium'>
                        {levelOptions}
                    </select>
                </div>
            );
        }
    });

    var LogsTable = React.createClass({
        handleShowMoreClick: function(e) {this.props.onShowMoreClick($(e.target).text())},
        handleShowAllClick: function() {this.props.onShowMoreClick('all')},
        render: function() {
            var tabRows = [],
                logsEntries = this.props.logsEntries;
            if (logsEntries && logsEntries.length) {
                tabRows = logsEntries.map(function(entry, i){
                    var key = logsEntries.length-i;
                    return  <tr key={key} className={entry[1].toLowerCase()}>
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
                    {this.props.logsHasMore &&
                        <tfoot className={'entries-skipped-msg'}>
                            <tr>
                                <td colSpan='3'>
                                    <span>{$.t('cluster_page.logs_tab.bottom_text')}
                                    </span>: {[100, 500, 1000, 5000].map(function(count) {
                                        return <span className='show-more-entries' onClick={this.handleShowMoreClick} key={count}> {count} </span>
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