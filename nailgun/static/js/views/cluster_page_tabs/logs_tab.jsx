/*
 * Copyright 2013 Mirantis, Inc.
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
    'views/common',
    'jsx!component_mixins'
],
function(React, utils, models, common, componentMixins) {
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
            if (to && logsEntries) {
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
                logsEntriesHasMore: false,
                logsLoading: false,
                to: 0
            };
        },
        getFirstNode: function() {
            if (this.props.model.get('nodes').length) {
                return _.find(this.props.model.get('nodes').models).id;
            }
            return null;
        },
        fetchSources: function(type, nodeId) {
            var cluster = this.props.model,
                chosenNode = nodeId ? nodeId : this.getFirstNode();
            this.sources = new models.LogSources();
            if (type == 'remote') {
                this.sources.deferred = this.sources.fetch({url: '/api/logs/sources/nodes/' + chosenNode});
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
                    chosenNodeId = null,
                    chosenLevelId = null;
                if (this.sources.length) {
                    if (type == 'local') {
                        chosenSourceId = _.find(this.sources.models, function(source) {return !source.get('remote')}).get('id');
                    } else {
                        chosenSourceId = _.find(this.sources.models, function(source) {return source.get('remote')}).get('id');
                        chosenNodeId = chosenNode;
                    }
                    chosenLevelId = _.find(this.sources.get(chosenSourceId).get('levels'))
                }
                this.setState({
                    sourcesFetchFail: undefined,
                    chosenNode: chosenNodeId,
                    chosenSource: chosenSourceId,
                    chosenLevel: chosenLevelId
                });
            }, this));
            this.sources.deferred.fail(_.bind(function() {
                this.setState({sourcesFetchFail: true});
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

            this.setState({logsLoading: true});
            this.props.model.set({'log_options': options}, {silent: true});
            app.navigate('#cluster/' + this.props.model.id + '/logs/' + utils.serializeTabOptions(options), {trigger: false, replace: true});

            this.fetchLogs(params)
                .done(_.bind(function(data) {
                    var has_more = false;
                    if (data.entries.length) {
                        has_more = data.has_more;
                    }
                    this.setState({
                        logsFetchFail: undefined,
                        logsEntriesHasMore: has_more,
                        logsEntries: data.entries,
                        buttonDisabled: true,
                        logsLoading: false,
                        to: data.to
                    });
                }, this))
                .fail(_.bind(function() {
                    this.setState({
                        logsFetchFail: true,
                        logsEntries: undefined,
                        buttonDisabled: false,
                        logsLoading: false
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
                buttonDisabled: false
            })},
        handleLevelUpdate: function(value) {
            this.setState({
                chosenLevel: value,
                buttonDisabled: false
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
                    <h3 data-i18n='cluster_page.logs_tab.title'></h3>
                    <div className='row'>
                        <div className='filter-bar'>
                            <SelectType cluster={this.props.model} updateType={this.handleTypeUpdate} />
                            <SelectNode cluster={this.props.model} updateNode={this.handleNodeUpdate} chosenType={this.state.chosenType} />
                            <SelectSource cluster={this.props.model} updateSource={this.handleSourceUpdate} chosenType={this.state.chosenType} sources={sources} />
                            <SelectLevel cluster={this.props.model} updateLevel={this.handleLevelUpdate} chosenSource={this.state.chosenSource} sources={sources} />
                            <div className='filter-bar-item'>
                                 <button
                                    className='filter-bar-btn show-logs-btn btn'
                                    onClick={this.onShowButtonClick}
                                    disabled={!this.state.chosenSource || this.state.buttonDisabled ? 'disabled' : ''}>
                                    {$.t('cluster_page.logs_tab.show')}
                                </button>
                            </div>
                        </div>
                    </div>
                    {this.state.logsFetchFail &&
                        <div className='logs-fetch-error alert alert-error'>{$.t('cluster_page.logs_tab.log_alert')}</div>
                    }
                    {this.state.sourcesFetchFail &&
                        <div className='node-sources-error alert alert-error'>{$.t('cluster_page.logs_tab.source_alert')}</div>
                    }
                    {this.state.logsEntries &&
                        <LogsTable
                            logsEntries={this.state.logsEntries}
                            logsEntriesHasMore={this.state.logsEntriesHasMore}
                            onShowMoreClick={this.onShowMoreClick} />
                    }
                    {this.state.logsLoading &&
                        <div className="logs-loading row row-fluid">
                            <div className="progress-bar">
                                <div className="progress progress-striped progress-success active"><div className="bar"></div></div>
                            </div>
                        </div>
                    }
                </div>
            );
        }
    })

    var SelectWrapper = React.createClass({
        render: function() {
            return (
                <div className={'filter-bar-item ' + this.props.className}>
                    <div className='filter-bar-label' style={this.props.style}>{this.props.title}</div>
                    {this.props.children}
                </div>
            );
        }
    });

    var SelectType = React.createClass({
        mixins: [React.BackboneMixin('cluster')],
        onTypeChange: function(e) {this.props.updateType(e.target.value)},
        render: function() {
            var types = [['local', 'Fuel Master']];
            if (this.props.cluster.get('nodes').length) {
                types.push(['remote', 'Other servers']);
            }
            var typeOptions = types.map(function(type, i){
                return <option value={type[0]} key={type[0]} >{type[1]}</option>;
            });
            return (
                <SelectWrapper title={$.t('cluster_page.logs_tab.logs')} className='log-type-filter'>
                    <select name='type' onChange={this.onTypeChange} className='filter-bar-dropdown input-medium'>
                        {typeOptions}
                    </select>
                </SelectWrapper>
            );
        }
    });

    var SelectNode = React.createClass({
        mixins: [React.BackboneMixin('cluster')],
        onNodeChange: function(e) {this.props.updateNode(e.target.value)},
        render: function() {
            var nodeOptions = this.props.cluster.get('nodes').map(function(node){
                    return <option value={node.id} key={node.id}>{node.get('name') || node.get('mac')}</option>;
                }, this),
                style = {display: (this.props.chosenType == 'local') ? 'none' : ''};
            return (
                <SelectWrapper title={$.t('cluster_page.logs_tab.node')} className='log-node-filter' style={style}>
                    <select name='node' onChange={this.onNodeChange} className='filter-bar-dropdown input-large' style={style}>
                        {nodeOptions}
                    </select>
                </SelectWrapper>
                );
        }
    });

    var SelectSource = React.createClass({
        mixins: [React.BackboneMixin('cluster')],
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
        onSourceChange: function(e) {this.props.updateSource(e.target.value)},
        render: function() {
            var sourceOptions = {};
            if (this.props.chosenType == 'local') {sourceOptions = this.getLocalSources();}
            else {sourceOptions = this.getRemoteSources();}
            return (
                <SelectWrapper title={$.t('cluster_page.logs_tab.source')} className='log-source-filter'>
                    <select name='source' onChange={this.onSourceChange} className='filter-bar-dropdown input-medium'>
                        {sourceOptions}
                    </select>
                </SelectWrapper>
            );
        }
    });

    var SelectLevel = React.createClass({
        mixins: [React.BackboneMixin('cluster')],
        onLevelChange: function(e) {this.props.updateLevel(e.target.value)},
        render: function() {
            var levelOptions = {};
            if (this.props.chosenSource && this.props.sources.length) {
                levelOptions = this.props.sources.get(this.props.chosenSource).get('levels').map(function(level){
                    return <option value={level} key={level}>{level}</option>;
                }, this);
            }
            return (
                <SelectWrapper title={$.t('cluster_page.logs_tab.level')} className='log-level-filter'>
                    <select name='level' onChange={this.onLevelChange} className='filter-bar-dropdown input-medium'>
                        {levelOptions}
                    </select>
                </SelectWrapper>
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
                    return  <tr key={key} className={'enable-selection ' + entry[1].toLowerCase()}>
                              <td className='nowrap'>{entry[0]}</td>
                              <td className='nowrap'>{entry[1]}</td>
                              <td><pre>{entry[2]}</pre></td>
                            </tr>;
                });
            }
            return (
                <table className='table table-bordered table-condensed table-logs'>
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
                    {this.props.logsEntriesHasMore &&
                        <tbody className={'entries-skipped-msg'}>
                            <tr>
                                <td colSpan='3'>
                                    <span>{$.t('cluster_page.logs_tab.bottom_text')}
                                    </span>: {[100, 500, 1000, 5000].map(function(count) {
                                        return <span className='show-more-entries' onClick={this.handleShowMoreClick} key={count}> {count} </span>
                                    }, this)}
                                    <span className='show-all-entries' onClick={this.handleShowAllClick}>{$.t('cluster_page.logs_tab.all_logs')}</span>
                                </td>
                            </tr>
                        </tbody>
                    }
                    {!logsEntries.length &&
                        <tbody className='no-logs-msg'>
                            <tr>
                                <td colSpan='3' >{$.t('cluster_page.logs_tab.no_log_text')}</td>
                            </tr>
                        </tbody>
                    }
                </table>
            );
        }
    });

    return LogsTab;
});