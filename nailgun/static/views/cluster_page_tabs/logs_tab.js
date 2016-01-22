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
import $ from 'jquery';
import _ from 'underscore';
import i18n from 'i18n';
import React from 'react';
import utils from 'utils';
import models from 'models';
import {Input, ProgressBar} from 'views/controls';
import {pollingMixin} from 'component_mixins';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import ReactFragment from 'react-addons-create-fragment';

var LogsTab = React.createClass({
  mixins: [
    pollingMixin(5)
  ],
  shouldDataBeFetched() {
    return this.state.to && this.state.logsEntries;
  },
  fetchData() {
    var request;
    var logsEntries = this.state.logsEntries;
    var from = this.state.from;
    var to = this.state.to;
    request = this.fetchLogs({from: from, to: to})
      .done((data) => {
        this.setState({
          logsEntries: data.entries.concat(logsEntries),
          from: data.from,
          to: data.to
        });
      });
    return $.when(request);
  },
  getInitialState() {
    return {
      showMoreLogsLink: false,
      loading: 'loading',
      loadingError: null,
      from: -1,
      to: 0
    };
  },
  fetchLogs(data) {
    return $.ajax({
      url: '/api/logs',
      dataType: 'json',
      data: _.extend(_.omit(this.props.selectedLogs, 'type'), data),
      headers: {
        'X-Auth-Token': app.keystoneClient.token
      }
    });
  },
  showLogs(params) {
    this.stopPolling();
    var logOptions = this.props.selectedLogs.type === 'remote' ? _.extend({}, this.props.selectedLogs) : _.omit(this.props.selectedLogs, 'node');
    logOptions.level = logOptions.level.toLowerCase();
    app.navigate('#cluster/' + this.props.cluster.id + '/logs/' + utils.serializeTabOptions(logOptions), {trigger: false, replace: true});
    params = params || {};
    this.fetchLogs(params)
      .done((data) => {
        var logsEntries = this.state.logsEntries || [];
        this.setState({
          showMoreLogsLink: data.has_more || false,
          logsEntries: params.fetch_older ? logsEntries.concat(data.entries) : data.entries,
          loading: 'done',
          from: data.from,
          to: data.to
        });
        this.startPolling();
      })
      .fail((response) => {
        this.setState({
          logsEntries: undefined,
          loading: 'fail',
          loadingError: utils.getResponseText(response, i18n('cluster_page.logs_tab.log_alert'))
        });
      });
  },
  onShowButtonClick() {
    this.setState({
      loading: 'loading',
      loadingError: null
    }, this.showLogs);
  },
  onShowMoreClick(value) {
    this.showLogs({max_entries: value, fetch_older: true, from: this.state.from});
  },
  render() {
    return (
      <div className='row'>
        <div className='title'>{i18n('cluster_page.logs_tab.title')}</div>
        <div className='col-xs-12 content-elements'>
          <LogFilterBar
            {... _.pick(this.props, 'selectedLogs', 'changeLogSelection')}
            nodes={this.props.cluster.get('nodes')}
            showLogs={this.showLogs}
            onShowButtonClick={this.onShowButtonClick}
          />
          {this.state.loading === 'fail' &&
            <div className='logs-fetch-error alert alert-danger'>
              {this.state.loadingError}
            </div>
          }
          {this.state.loading === 'loading' && <ProgressBar />}
          {this.state.logsEntries &&
            <LogsTable
              logsEntries={this.state.logsEntries}
              showMoreLogsLink={this.state.showMoreLogsLink}
              onShowMoreClick={this.onShowMoreClick}
            />
          }
        </div>
      </div>
    );
  }
});

var LogFilterBar = React.createClass({
  // PureRenderMixin added for prevention the rerender LogFilterBar (because of polling) in Mozilla browser
  mixins: [PureRenderMixin],
  getInitialState() {
    return _.extend({}, this.props.selectedLogs, {
      sourcesLoadingState: 'loading',
      sourcesLoadingError: null,
      sources: [],
      locked: true
    });
  },
  fetchSources(type, nodeId) {
    var nodes = this.props.nodes;
    var chosenNodeId = nodeId || (nodes.length ? nodes.first().id : null);
    this.sources = new models.LogSources();
    this.sources.deferred = (type === 'remote' && chosenNodeId) ?
      this.sources.fetch({url: '/api/logs/sources/nodes/' + chosenNodeId})
    :
      this.sources.fetch();
    this.sources.deferred.done(() => {
      var filteredSources = this.sources.filter((source) => source.get('remote') === (type !== 'local'));
      var chosenSource = _.findWhere(filteredSources, {id: this.state.source}) || _.first(filteredSources);
      var chosenLevelId = chosenSource ? _.contains(chosenSource.get('levels'), this.state.level) ? this.state.level : _.first(chosenSource.get('levels')) : null;
      this.setState({
        type: type,
        sources: this.sources,
        sourcesLoadingState: 'done',
        node: chosenNodeId && type === 'remote' ? chosenNodeId : null,
        source: chosenSource ? chosenSource.id : null,
        level: chosenLevelId,
        locked: false
      });
    });
    this.sources.deferred.fail((response) => {
      this.setState({
        type: type,
        sources: {},
        sourcesLoadingState: 'fail',
        sourcesLoadingError: utils.getResponseText(response, i18n('cluster_page.logs_tab.source_alert')),
        locked: false
      });
    });
    return this.sources.deferred;
  },
  componentDidMount() {
    this.fetchSources(this.state.type, this.state.node)
      .done(() => {
        this.setState({locked: true});
        this.props.showLogs();
      });
  },
  onTypeChange(name, value) {
    this.fetchSources(value);
  },
  onNodeChange(name, value) {
    this.fetchSources('remote', value);
  },
  onLevelChange(name, value) {
    this.setState({
      level: value,
      locked: false
    });
  },
  onSourceChange(name, value) {
    var levels = this.state.sources.get(value).get('levels');
    var data = {locked: false, source: value};
    if (!_.contains(levels, this.state.level)) data.level = _.first(levels);
    this.setState(data);
  },
  getLocalSources() {
    return this.state.sources.map((source) => {
      if (!source.get('remote')) {
        return <option value={source.id} key={source.id}>{source.get('name')}</option>;
      }
    }, this);
  },
  getRemoteSources() {
    var options = {};
    var groups = [''];
    var sourcesByGroup = {'': []};
    var sources = this.state.sources;
    if (sources.length) {
      sources.each((source) => {
        var group = source.get('group') || '';
        if (!_.has(sourcesByGroup, group)) {
          sourcesByGroup[group] = [];
          groups.push(group);
        }
        sourcesByGroup[group].push(source);
      });
      _.each(groups, (group) => {
        if (sourcesByGroup[group].length) {
          var option = sourcesByGroup[group].map((source) => {
            return <option value={source.id} key={source.id}>{source.get('name')}</option>;
          });
          options[group] = group ? <optgroup label={group}>{option}</optgroup> : option;
        }
      }, this);
    }
    return ReactFragment(options);
  },
  handleShowButtonClick() {
    this.setState({locked: true});
    this.props.changeLogSelection(_.pick(this.state, 'type', 'node', 'source', 'level'));
    this.props.onShowButtonClick();
  },
  render() {
    var isRemote = this.state.type === 'remote';
    return (
      <div className='well well-sm'>
        <div className='sticker row'>
          {this.renderTypeSelect()}
          {isRemote && this.renderNodeSelect()}
          {this.renderSourceSelect()}
          {this.renderLevelSelect()}
          {this.renderFilterButton(isRemote)}
        </div>
        {this.state.sourcesLoadingState === 'fail' &&
          <div className='node-sources-error alert alert-danger'>
            {this.state.sourcesLoadingError}
          </div>
        }
      </div>
    );
  },
  renderFilterButton(isRemote) {
    return <div className={utils.classNames({
      'form-group': true,
      'col-md-4 col-sm-12': isRemote,
      'col-md-6 col-sm-3': !isRemote
    })}>
      <label />
      <button
        className='btn btn-default pull-right'
        onClick={this.handleShowButtonClick}
        disabled={!this.state.source || this.state.locked}
      >
        {i18n('cluster_page.logs_tab.show')}
      </button>
    </div>;
  },
  renderTypeSelect() {
    var types = [['local', 'Fuel Master']];
    if (this.props.nodes.length) {
      types.push(['remote', 'Other servers']);
    }
    var typeOptions = types.map((type) => {
      return <option value={type[0]} key={type[0]}>{type[1]}</option>;
    });
    return <div className='col-md-2 col-sm-3'>
      <Input
        type='select'
        label={i18n('cluster_page.logs_tab.logs')}
        value={this.state.type}
        wrapperClassName='filter-bar-item log-type-filter'
        name='type'
        onChange={this.onTypeChange}
        children={typeOptions}
      />
    </div>;
  },
  renderNodeSelect() {
    var sortedNodes = this.props.nodes.models.sort(_.partialRight(utils.compare, {attr: 'name'}));
    var nodeOptions = sortedNodes.map((node) => {
      return <option value={node.id} key={node.id}>{node.get('name') || node.get('mac')}</option>;
    });

    return <div className='col-md-2 col-sm-3'>
      <Input
        type='select'
        label={i18n('cluster_page.logs_tab.node')}
        value={this.state.node}
        wrapperClassName='filter-bar-item log-node-filter'
        name='node'
        onChange={this.onNodeChange}
        children={nodeOptions}
      />
    </div>;
  },
  renderSourceSelect() {
    var sourceOptions = this.state.type === 'local' ? this.getLocalSources() : this.getRemoteSources();
    return <div className='col-md-2 col-sm-3'>
      <Input
        type='select'
        label={i18n('cluster_page.logs_tab.source')}
        value={this.state.source}
        wrapperClassName='filter-bar-item log-source-filter'
        name='source'
        onChange={this.onSourceChange}
        disabled={!this.state.source}
        children={sourceOptions}
      />
    </div>;
  },
  renderLevelSelect() {
    var levelOptions = [];
    if (this.state.source && this.state.sources.length) {
      levelOptions = this.state.sources.get(this.state.source).get('levels').map((level) => {
        return <option value={level} key={level}>{level}</option>;
      });
    }
    return <div className='col-md-2 col-sm-3'>
      <Input
        type='select'
        label={i18n('cluster_page.logs_tab.min_level')}
        value={this.state.level}
        wrapperClassName='filter-bar-item log-level-filter'
        name='level'
        onChange={this.onLevelChange}
        disabled={!this.state.level}
        children={levelOptions}
      />
    </div>;
  }
});

var LogsTable = React.createClass({
  handleShowMoreClick(value) {
    return this.props.onShowMoreClick(value);
  },
  getLevelClass(level) {
    return {
      DEBUG: 'debug',
      INFO: 'info',
      NOTICE: 'notice',
      WARNING: 'warning',
      ERROR: 'error',
      ERR: 'error',
      CRITICAL: 'critical',
      CRIT: 'critical',
      ALERT: 'alert',
      EMERG: 'emerg'
    }[level];
  },
  render() {
    var tabRows = [];
    var logsEntries = this.props.logsEntries;
    if (logsEntries && logsEntries.length) {
      tabRows = _.map(logsEntries, (entry, index) => {
        var key = logsEntries.length - index;
        return <tr key={key} className={this.getLevelClass(entry[1])}>
          <td>{entry[0]}</td>
          <td>{entry[1]}</td>
          <td>{entry[2]}</td>
        </tr>;
      });
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
                <div>
                  <span>{i18n('cluster_page.logs_tab.bottom_text')}</span>:
                  {
                    [100, 500, 1000, 5000].map((count) => {
                      return <button className='btn btn-link show-more-entries' onClick={_.bind(this.handleShowMoreClick, this, count)} key={count}>{count}</button>;
                    })
                  }
                </div>
              </td>
            </tr>
          </tfoot>
        }
      </table>
      :
      <div className='no-logs-msg'>{i18n('cluster_page.logs_tab.no_log_text')}</div>;
  }
});

export default LogsTab;
