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

    var LogsTab = React.createClass({
        mixins: [
            React.addons.LinkedStateMixin,
            React.BackboneMixin('model')
        ],
        getInitialState: function() {
            return {chosenType: 'local'};
        },
        onTypeChange: function() {
            var chosenType = this.$('select[name=type]').val();
            this.$('.log-node-filter').toggle(chosenType == 'remote');
            this.fetchSources(chosenType);
        },
        onNodeChange: function() {
            this.fetchSources('remote');
        },
        fetchSources: function(type) {
            var input = this.$('select[name=source]');
            this.$('select[name=source], select[name=level]').html('').attr('disabled', true);
            this.updateShowButtonState();
            this.sources = new models.LogSources();
            if (type == 'remote') {
                this.sources.deferred = this.sources.fetch({url: '/api/logs/sources/nodes/' + this.$('select[name=node]').val()});
            } else if (!this.model.get('log_sources')) {
                this.sources.deferred = this.sources.fetch();
                this.sources.deferred.done(_.bind(function() {
                    this.model.set('log_sources', this.sources.toJSON());
                }, this));
            } else {
                this.sources.reset(this.model.get('log_sources'));
                this.sources.deferred = $.Deferred();
                this.sources.deferred.resolve();
            }
            this.sources.deferred.done(_.bind(type == 'local' ? this.updateLocalSources : this.updateRemoteSources, this));
            this.sources.deferred.done(_.bind(function() {
                if (this.sources.length) {
                    input.attr('disabled', false);
                    this.updateShowButtonState();
                    this.updateLevels();
                }
            }, this));
            this.sources.deferred.fail(_.bind(function() {
                this.$('.node-sources-error').show();
            }, this));
            return this.sources.deferred;
        },
        updateSources: function() {
            var chosenType = this.$('select[name=type]').val();
            if (chosenType == 'local') {
                this.updateLocalSources();
            } else {
                this.updateRemoteSources();
            }
        },
        updateLocalSources: function() {
            var input = this.$('select[name=source]');
            this.sources.each(function(source) {
                if (!source.get('remote')) {
                    var option = $('<option/>', {value: source.id, text: source.get('name')});
                    if (source.get('name') == this.lastSource){
                        option.attr('selected', 'selected');
                    }
                    input.append(option);
                }
            }, this);
        },
        updateRemoteSources: function() {
            var input = this.$('select[name=source]');
            var groups = [''], sourcesByGroup = {'': []};
            this.sources.each(function(source) {
                var group = source.get('group') || '';
                if (!_.has(sourcesByGroup, group)) {
                    sourcesByGroup[group] = [];
                    groups.push(group);
                }
                sourcesByGroup[group].push(source);
            });
            _.each(groups, function(group) {
                if (sourcesByGroup[group].length) {
                    var el = group ? $('<optgroup/>', {label: group}).appendTo(input) : input;
                    _.each(sourcesByGroup[group], function(source) {
                        var option = $('<option/>', {value: source.id, text: source.get('name')});
                        if (source.get('name') == this.lastSource){
                            option.attr('selected', 'selected');
                        }
                        el.append(option);
                    }, this);
                }
            }, this);
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
        render: function() {
            var cluster = this.props.model,
                types = [['local', 'Fuel Master']];
            if (cluster.get('nodes').length) {
                types.push(['remote', 'Other servers']);
            }

            var typeOptions = types.map(function(type, i){
                return <option value={type[0]} key={type[0]} >{type[1]}</option>;
            });
            return (
                <div className="wrapper">
                    <h3 data-i18n="cluster_page.logs_tab.title"></h3>
                    <div className="row">
                        <div className="filter-bar">
                            <div className="filter-bar-item log-type-filter">
                                <div className="filter-bar-label" data-i18n="cluster_page.logs_tab.logs"></div>
                                <select onChange={this.onTypeChange} className="filter-bar-dropdown input-medium">
                                    {typeOptions}
                                </select>
                            </div>
                        </div>
                    </div>

                    <div className="logs-fetch-error alert alert-error hide" data-i18n="cluster_page.logs_tab.log_alert">
                        Unable to fetch logs.
                    </div>
                    <div className="node-sources-error alert alert-error hide" data-i18n="cluster_page.logs_tab.source_alert">
                        Unable to fetch log sources.
                    </div>

                    <table className="table table-bordered table-condensed table-logs hide">
                      <thead>
                        <tr>
                          <th nowrap data-i18n="cluster_page.logs_tab.date">Date</th>
                          <th nowrap data-i18n="cluster_page.logs_tab.level"></th>
                          <th data-i18n="cluster_page.logs_tab.message"></th>
                        </tr>
                      </thead>
                      <tbody className="entries-skipped-msg">
                        <tr>
                          <td colSpan="3">
                            <span data-i18n="cluster_page.logs_tab.bottom_text">
                            </span>:
                            <span className="show-all-entries" data-i18n="cluster_page.logs_tab.all_logs"></span>
                          </td>
                        </tr>
                      </tbody>
                      <tbody className="log-entries"></tbody>
                      <tbody className="no-logs-msg">
                        <tr>
                          <td colSpan="3" data-i18n="cluster_page.logs_tab.no_log_text"></td>
                        </tr>
                      </tbody>
                    </table>

                    <div className="logs-loading row row-fluid hide">
                      <div className="progress-bar">
                        <div className="progress progress-striped progress-success active"><div className="bar"></div></div>
                      </div>
                    </div>
                </div>
            );
        }
    })
        

    return LogsTab;
});
