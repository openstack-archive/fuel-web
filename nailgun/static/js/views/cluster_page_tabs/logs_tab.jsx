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
                chosenNode: this.getFirtsNode()
            };
        },
        getFirtsNode: function() {
            if (this.props.model.get('nodes').length) {
                return _.find(this.props.model.get('nodes').models);
            }
            return null;
        },
        fetchSources: function(type) {
            console.log('type1', type);
            //console.log('cluster', this.props.model);
            var cluster = this.props.model;
            //var input = this.$('select[name=source]');
            //this.$('select[name=source], select[name=level]').html('').attr('disabled', true);
            //this.updateShowButtonState();
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
                if (this.sources.length) {
                    //this.setState({chosenNode: 'dddd'});
                    //input.attr('disabled', false);
                    //this.updateShowButtonState();
                    //this.updateLevels();
                }
            }, this));
            this.sources.deferred.fail(_.bind(function() {
                //this.$('.node-sources-error').show();
            }, this));
            this.setState({sourcesFetched: true});
            return this.sources.deferred;
        },
        componentDidMount: function() {
            if (!this.state.sourcesFetched) {
                this.fetchSources();
            }
        },
        updateLevels: function(e) {
            var input = this.$('select[name=level]');
            if (e) {
                this.lastSource = this.$('select[name=source]').val();
            } else {
                this.$('select[name=source]').val(this.lastSource);
            }
            var chosenSourceId = this.$('select[name=source]').val();
            if (chosenSourceId) {
                input.html('').attr('disabled', false);
                var source = this.sources.get(chosenSourceId);
                _.each(source.get('levels'), function(level) {
                    var option = $('<option/>').text(level);
                    if (level == this.lastLogLevel){
                        option.attr('selected', 'selected');
                    }
                    input.append(option);
                }, this);
            }
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
                            <SelectSource cluster={this.props.model} updateSource={this.handleSourceUpdate} chosenType={this.state.chosenType} sources={this.sources}/>
                            <SelectLevel cluster={this.props.model} updateSource={this.handleLevelUpdate} sources={this.sources}/>
                        </div>
                    </div>
                </div>
            );
        }
    })

    var Filter = React.createClass({
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
            var cluster = this.props.cluster,
                types = [['local', 'Fuel Master']];
            if (cluster.get('nodes').length) {
                types.push(['remote', 'Other servers']);
            }
            var typeOptions = types.map(function(type, i){
                return <option value={type[0]} key={type[0]} >{type[1]}</option>;
            });
            return (
                <Filter title={$.t('cluster_page.logs_tab.logs')} className="log-type-filter">
                    <select onChange={this.handleFilterChange} className="filter-bar-dropdown input-medium">
                        {typeOptions}
                    </select>
                </Filter>
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
            var nodeOptions = this.props.cluster.get('nodes').map(function(node, i){
                    return <option value={node.id} key={node.id}>{node.get('name') || node.get('mac')}</option>;
                }, this);
            return (
                <div>
                {(this.props.chosenType != 'local') &&
                    <Filter title={$.t('cluster_page.logs_tab.node')} className="log-node-filter">
                        <select onChange={this.onNodeChange} className="filter-bar-dropdown input-large">
                            {nodeOptions}
                        </select>
                    </Filter>
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
        onSourceChange: function(e) {
            var value = e.target.value;
            this.props.updateSource(value);
        },
        render: function() {
            var sources = this.props.sources || {};
            if (sources.length) {
                var sourceOptions = sources.map(function(source, i){
                    return <option value={source.id} key={source.id}>{source.get('name')}</option>;
                }, this);
            } else var sourceOptions = {};
            
            return (
                <Filter title={$.t('cluster_page.logs_tab.source')} className="log-source-filter">
                    <select onChange={this.onSourceChange} className="filter-bar-dropdown input-medium">
                        {sourceOptions}
                    </select>
                </Filter>
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
            
            return (
                <Filter title={$.t('cluster_page.logs_tab.level')} className="log-level-filter">
                    <select onChange={this.onLevelChange} className="filter-bar-dropdown input-medium">
                        {levelOptions}
                    </select>
                </Filter>
            );
        }
    });

    return LogsTab;
});
