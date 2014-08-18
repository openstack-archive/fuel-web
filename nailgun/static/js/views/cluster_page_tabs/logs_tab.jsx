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
    'models'
],
function(React, utils, models) {
    'use strict';

    var LogTabMixin = {
    };

    var LogsTab = React.createClass({
        mixins: [
            LogTabMixin,
            React.addons.LinkedStateMixin,
            React.BackboneMixin('model')
        ],
        getInitialState: function() {
            return {
                chosenType: 'local',
                chosenNode: this.getFirtsNode(),
                chosenSource: null,
                sources: {}
            };
        },
        getFirtsNode: function() {
            if (this.props.model.get('nodes').length) {
                return _.find(this.props.model.get('nodes').models);
            }
            return null;
        },
        fetchSources: function(type) {
            var cluster = this.props.model;
            this.sources = new models.LogSources();
            if (type == 'remote') {
                this.sources.deferred = this.sources.fetch({url: '/api/logs/sources/nodes/' + this.state.chosenNode});
            } else if (!cluster.get('log_sources')) {
                this.sources.deferred = this.sources.fetch();
                this.sources.deferred.done(_.bind(function() {
                    cluster.set('log_sources', this.sources.toJSON());
                }, this));
            } else {
                this.sources.reset(cluster.get('log_sources'));
                this.sources.deferred = $.Deferred();
                this.sources.deferred.resolve();
            }
            this.sources.deferred.done(_.bind(function() {
                this.setState({sources: this.sources});
                if (this.sources.length) {
                    if (type == 'local') {
                        this.setState({chosenSource: _.find(this.sources.models, function(source) {return !source.get('remote')}).get('id')});
                    } else {
                        this.setState({chosenSource: _.find(this.sources.models, function(source) {return source.get('remote')}).get('id')});
                    }
                }
            }, this));
            this.sources.deferred.fail(_.bind(function() {
                this.setState({sources: {}});
            }, this));
            this.setState({sourcesFetched: true});
            return this.sources.deferred;
        },
        componentDidMount: function() {
            if (!this.state.sourcesFetched) {
                this.fetchSources(this.state.chosenType);
            }
        },
        onShowButtonClick: function() {
            this.showLogs({truncate_log: true});
        },
        showLogs: function(params) {
            this.rejectRegisteredDeferreds();
            this.to = 0;

            var options = this.getOptions();
            this.model.set({'log_options': options}, {silent: true});
            app.navigate('#cluster/' + this.model.id + '/logs/' + utils.serializeTabOptions(options), {trigger: false, replace: true});

            // this.$('.logs-fetch-error, .node-sources-error').hide();
            // if (!this.reversed) {
            //     this.$('.table-logs').hide();
            // } else {
            //     this.$('.table-logs .entries-skipped-msg').hide();
            // }
            // this.$('.logs-loading').show();
            // this.$('select').attr('disabled', true);
            // this.$('.show-logs-btn').addClass('disabled');

            this.fetchLogs(params)
                .done(_.bind(function(data) {
                    this.$('.table-logs .log-entries').html('');
                    if (data.entries.length) {
                        if (data.has_more) {
                            this.showEntriesSkippedMsg();
                        } else {
                            this.$('.table-logs .entries-skipped-msg').hide();
                        }
                        this.appendLogEntries(data, true);
                    } else {
                        this.$('.table-logs .no-logs-msg').show();
                        this.$('.table-logs .entries-skipped-msg').hide();
                    }
                    this.$('.table-logs').show();
                    this.scheduleUpdate();
                }, this))
                .fail(_.bind(function() {
                    this.$('.table-logs').hide();
                    this.$('.logs-fetch-error').show();
                    this.$('.show-logs-btn').removeClass('disabled');
                }, this))
                .always(_.bind(function() {
                    this.$('.logs-loading').hide();
                    this.$('select').attr('disabled', false);
                }, this));
        },
        showEntriesSkippedMsg: function() {
            var el = this.$('.table-logs .entries-skipped-msg');
            el.show();
            el.find('.show-more-entries').remove();
            _.each([100, 500, 1000, 5000], function(count) {
                el.find('.show-all-entries').before($('<span/>', {'class': 'show-more-entries', text: count}));
            }, this);
        },
        appendLogEntries: function(data, doNotScroll) {
            this.to = data.to;
            if (data.entries.length) {
                if (!this.reversed) {
                    data.entries.reverse();
                }
                // autoscroll only if window is already scrolled to bottom
                var scrollToBottom = !this.reversed && !doNotScroll && $(document).height() == $(window).scrollTop() + $(window).height();

                this.$('.table-logs .no-logs-msg').hide();
                this.$('.table-logs .log-entries')[this.reversed ? 'prepend' : 'append'](_.map(data.entries, function(entry) {
                    return this.logEntryTemplate({entry: entry});
                }, this).join(''));

                if (scrollToBottom) {
                    $(window).scrollTop($(document).height());
                }
            }
        },
        getOptions: function() {
            var options = {};
            options.type = this.chosenType;
            if (options.type == 'remote') {
                options.node = this.chosenNodeId;
            }
            options.source = this.chosenSourceId;
            options.level = this.chosenLevel.toLowerCase();
            return options;
        },
        handleTypeUpdate: function(value) {
            this.setState({chosenType: value});
            this.fetchSources(value);
        },
        handleNodeUpdate: function(value) {
            this.setState({chosenNode: value});
        },
        handleSourceUpdate: function(value) {
            this.setState({chosenSource: value});
        },
        handleLevelUpdate: function(value) {
            this.setState({chosenLevel: value});
        },
        render: function() {
            return (
                <div className="wrapper">
                    <h3 data-i18n="cluster_page.logs_tab.title"></h3>
                    <div className="row">
                        <div className="filter-bar">
                            <SelectType cluster={this.props.model} updateType={this.handleTypeUpdate} />
                            <SelectNode cluster={this.props.model} updateNode={this.handleNodeUpdate} chosenType={this.state.chosenType}  />
                            <SelectSource cluster={this.props.model} updateSource={this.handleSourceUpdate} chosenType={this.state.chosenType} sources={this.state.sources}/>
                            <SelectLevel cluster={this.props.model} updateLevel={this.handleLevelUpdate} chosenSource={this.state.chosenSource} sources={this.state.sources}/>
                            <div className="filter-bar-item">
                                 <button 
                                    className="filter-bar-btn show-logs-btn btn"
                                    onClick={this.showLogs}>
                                    {$.t('cluster_page.logs_tab.show')}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    })

    var SelectWrapper = React.createClass({
        render: function() {
            return (
                <div className={'filter-bar-item ' + this.props.className}>
                    <div className="filter-bar-label">{this.props.title}</div>
                    {this.props.children}
                </div>
            );
        }
    });

    var SelectType = React.createClass({
        mixins: [
            LogTabMixin,
            React.BackboneMixin('cluster')
        ],
        handleFilterChange: function(e){
            var value = e.target.value;
            this.props.updateType(value);
        },
        render: function() {
            var types = [['local', 'Fuel Master']];
            if (this.props.cluster.get('nodes').length) {
                types.push(['remote', 'Other servers']);
            }
            var typeOptions = types.map(function(type, i){
                return <option value={type[0]} key={type[0]} >{type[1]}</option>;
            });
            return (
                <SelectWrapper title={$.t('cluster_page.logs_tab.logs')} className="log-type-filter">
                    <select onChange={this.handleFilterChange} className="filter-bar-dropdown input-medium">
                        {typeOptions}
                    </select>
                </SelectWrapper>
            );
        }
    });

    var SelectNode = React.createClass({
        mixins: [
            LogTabMixin,
            React.BackboneMixin('cluster')
        ],
        onNodeChange: function(e) {
            var value = e.target.value;
            this.props.updateNode(value);
        },
        render: function() {
            var nodeOptions = this.props.cluster.get('nodes').map(function(node){
                    return <option value={node.id} key={node.id}>{node.get('name') || node.get('mac')}</option>;
                }, this);
            return (
                <div>
                {(this.props.chosenType != 'local') &&
                    <SelectWrapper title={$.t('cluster_page.logs_tab.node')} className="log-node-filter">
                        <select onChange={this.onNodeChange} className="filter-bar-dropdown input-large">
                            {nodeOptions}
                        </select>
                    </SelectWrapper>
                }
                </div>
            );
        }
    });

    var SelectSource = React.createClass({
        mixins: [
            LogTabMixin,
            React.BackboneMixin('cluster')
        ],
        getLocalSources: function() {
            var options = {},
                sources = this.props.sources;
            if (sources.length) {
                options = sources.map(function(source){
                    if (!source.get('remote')) {
                        return <option value={source.id} key={source.id}>{source.get("name")}</option>;
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
        onSourceChange: function(e) {
            var value = e.target.value;
            this.props.updateSource(value);
        },
        render: function() {
            var sourceOptions = {};
            if (this.props.chosenType == 'remote') {
                sourceOptions = this.getRemoteSources();
            } else {
                sourceOptions = this.getLocalSources();
            }
            return (
                <SelectWrapper title={$.t('cluster_page.logs_tab.source')} className="log-source-filter">
                    <select onChange={this.onSourceChange} className="filter-bar-dropdown input-medium">
                        {sourceOptions}
                    </select>
                </SelectWrapper>
            );
        }
    });

    var SelectLevel = React.createClass({
        mixins: [
            LogTabMixin,
            React.BackboneMixin('cluster')
        ],
        onLevelChange: function(e) {
            var value = e.target.value;
            this.props.updateLevel(value);
        },
        render: function() {
            var levelOptions = {};
            if (this.props.chosenSource && this.props.sources.length) {
                var source = this.props.sources.get(this.props.chosenSource);
                levelOptions = source.get('levels').map(function(level){
                    return <option value={level} key={level}>{level}</option>;
                }, this);
            }
            return (
                <SelectWrapper title={$.t('cluster_page.logs_tab.level')} className="log-level-filter">
                    <select onChange={this.onLevelChange} className="filter-bar-dropdown input-medium">
                        {levelOptions}
                    </select>
                </SelectWrapper>
            );
        }
    });
    return LogsTab;
});