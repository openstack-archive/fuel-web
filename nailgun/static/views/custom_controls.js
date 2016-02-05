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
import _ from 'underscore';
import i18n from 'i18n';
import React from 'react';
import ReactDOM from 'react-dom';
import utils from 'utils';
import {Input, Tooltip} from 'views/controls';

var customControls = {};

customControls.custom_repo_configuration = React.createClass({
  statics: {
    // validate method represented as static method to support cluster settings validation
    validate(setting, models) {
      var ns = 'cluster_page.settings_tab.custom_repo_configuration.errors.';
      var nameRegexp = /^[\w-.]+$/;
      var os = models.release.get('operating_system');
      var errors = setting.value.map((repo) => {
        var error = {};
        var value = this.repoToString(repo, os);
        if (!repo.name) {
          error.name = i18n(ns + 'empty_name');
        } else if (!repo.name.match(nameRegexp)) {
          error.name = i18n(ns + 'invalid_name');
        }
        if (!value || !value.match(this.defaultProps.repoRegexes[os])) {
          error.uri = i18n(ns + 'invalid_repo');
        }
        var priority = repo.priority;
        if (
          _.isNaN(priority) ||
          !_.isNull(priority) && (
            !(priority === _.parseInt(priority, 10)) ||
            os === 'CentOS' && (priority < 1 || priority > 99)
          )
        ) {
          error.priority = i18n(ns + 'invalid_priority');
        }
        return _.isEmpty(error) ? null : error;
      });
      return _.compact(errors).length ? errors : null;
    },
    repoToString(repo, os) {
      var repoData = _.compact(this.defaultProps.repoAttributes[os].map(
        (attribute) => repo[attribute]
      ));
      if (!repoData.length) return ''; // in case of new repo
      return repoData.join(' ');
    }
  },
  getInitialState() {
    return {};
  },
  getDefaultProps() {
    return {
      /* eslint-disable max-len */
      repoRegexes: {
        Ubuntu: /^(deb|deb-src)\s+(\w+:\/\/[\w\-.\/]+(?::\d+)?[\w\-.\/]+)\s+([\w\-.\/]+)(?:\s+([\w\-.\/\s]+))?$/i,
        CentOS: /^(\w+:\/\/[\w\-.\/]+(?::\d+)?[\w\-.\/]+)\s*$/i
      },
      /* eslint-enable max-len */
      repoAttributes: {
        Ubuntu: ['type', 'uri', 'suite', 'section'],
        CentOS: ['uri']
      }
    };
  },
  changeRepos(method, index, value) {
    value = _.trim(value).replace(/\s+/g, ' ');
    var repos = _.cloneDeep(this.props.value);
    var os = this.props.cluster.get('release').get('operating_system');
    switch (method) {
      case 'add':
        var data = {
          name: '',
          type: '',
          uri: '',
          priority: this.props.extra_priority
        };
        if (os === 'Ubuntu') {
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
        repos[index].priority = value === '' ? null : Number(value);
        break;
      default:
        var repo = repos[index];
        var match = value.match(this.props.repoRegexes[os]);
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
  renderDeleteButton(index) {
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
  render() {
    var ns = 'cluster_page.settings_tab.custom_repo_configuration.';
    var os = this.props.cluster.get('release').get('operating_system');
    return (
      <div className='repos' key={this.state.key}>
        {this.props.description &&
          <span
            className='help-block'
            dangerouslySetInnerHTML={{
              __html: utils.urlify(utils.linebreaks(_.escape(this.props.description)))
            }}
          />
        }
        {this.props.value.map((repo, index) => {
          var error = (this.props.error || {})[index];
          var props = {
            name: index,
            type: 'text',
            disabled: this.props.disabled
          };
          return (
            <div className='form-inline' key={'repo-' + index}>
              <Input
                {...props}
                defaultValue={repo.name}
                error={error && error.name}
                wrapperClassName='repo-name'
                onChange={this.changeRepos.bind(this, 'change_name')}
                label={index === 0 && i18n(ns + 'labels.name')}
                debounce
              />
              <Input
                {...props}
                defaultValue={this.constructor.repoToString(repo, os)}
                error={error && (error.uri ? error.name ? '' : error.uri : null)}
                onChange={this.changeRepos.bind(this, null)}
                label={index === 0 && i18n(ns + 'labels.uri')}
                wrapperClassName='repo-uri'
                debounce
              />
              <Input
                {...props}
                defaultValue={repo.priority}
                error={
                  error && (error.priority ? (error.name || error.uri) ? '' : error.priority : null)
                }
                wrapperClassName='repo-priority'
                onChange={this.changeRepos.bind(this, 'change_priority')}
                extraContent={index > 0 && this.renderDeleteButton(index)}
                label={index === 0 && i18n(ns + 'labels.priority')}
                placeholder={i18n(ns + 'placeholders.priority')}
                debounce
              />
            </div>
          );
        })}
        <div className='buttons'>
          <button
            key='addExtraRepo'
            className='btn btn-default btn-add-repo'
            onClick={this.changeRepos.bind(this, 'add')}
            disabled={this.props.disabled}
          >
            {i18n(ns + 'add_repo_button')}
          </button>
        </div>
      </div>
    );
  }
});

var multipleValuesInputMixin = {
  statics: {
    validate(setting) {
      if (!(setting.regex || {}).source) return null;
      var regex = new RegExp(setting.regex.source);
      var errors = _.map(setting.value,
        (value) => value.match(regex) ? null : setting.regex.error
      );
      return _.compact(errors).length ? errors : null;
    }
  },
  propTypes: {
    value: React.PropTypes.arrayOf(React.PropTypes.node).isRequired,
    type: React.PropTypes.oneOf(['text_list', 'password_list', 'textarea_list', 'file_list'])
      .isRequired,
    name: React.PropTypes.node,
    label: React.PropTypes.node,
    description: React.PropTypes.node,
    error: React.PropTypes.arrayOf(React.PropTypes.node),
    disabled: React.PropTypes.bool,
    wrapperClassName: React.PropTypes.node,
    onChange: React.PropTypes.func,
    minFieldsLength: React.PropTypes.number,
    tooltipPlacement: React.PropTypes.oneOf(['left', 'right', 'top', 'bottom']),
    tooltipIcon: React.PropTypes.node,
    tooltipText: React.PropTypes.node
  },
  getInitialState() {
    return {};
  },
  getDefaultProps() {
    return {
      minFieldsLength: 1,
      tooltipIcon: 'glyphicon-warning-sign',
      tooltipPlacement: 'right'
    };
  },
  changeField(index, method = 'change') {
    var value = _.clone(this.props.value);
    switch (method) {
      case 'add':
        value.splice(index + 1, 0, '');
        this.setState({key: _.now()});
        break;
      case 'remove':
        value.splice(index, 1);
        this.setState({key: _.now()});
        break;
      case 'change':
        var input = ReactDOM.findDOMNode(this.refs['input' + index]);
        value[index] = input.value;
        break;
    }
    if (this.props.onChange) return this.props.onChange(this.props.name, value);
  },
  debouncedFieldChange: _.debounce(function(index) {
    return this.changeField(index);
  }, 200, {leading: true}),
  renderMultipleInputControls(index) {
    return (
      <div className='field-controls'>
        <button
          className='btn btn-link btn-add-field'
          disabled={this.props.disabled}
          onClick={() => this.changeField(index, 'add')}
        >
          <i className='glyphicon glyphicon-plus-sign' />
        </button>
        {this.props.value.length > this.props.minFieldsLength &&
          <button
            className='btn btn-link btn-remove-field'
            disabled={this.props.disabled}
            onClick={() => this.changeField(index, 'remove')}
          >
            <i className='glyphicon glyphicon-minus-sign' />
          </button>
        }
      </div>
    );
  },
  renderLabel() {
    if (!this.props.label) return null;
    return (
      <label key='label'>
        {this.props.label}
        {this.props.tooltipText &&
          <Tooltip text={this.props.tooltipText} placement={this.props.tooltipPlacement}>
            <i className={utils.classNames('glyphicon tooltip-icon', this.props.tooltipIcon)} />
          </Tooltip>
        }
      </label>
    );
  },
  renderDescription() {
    if (this.props.error) return null;
    return <span key='description' className='help-block'>{this.props.description}</span>;
  },
  renderWrapper(children) {
    return (
      <div
        key={this.state.key}
        className={utils.classNames({
          'form-group': true,
          disabled: this.props.disabled,
          [this.props.wrapperClassName]: this.props.wrapperClassName
        })}
      >
        {children}
      </div>
    );
  },
  render() {
    return this.renderWrapper([
      this.renderLabel(),
      <div
        key='field-list'
        className={utils.classNames({
          'field-list': true,
          [this.props.type]: true
        })}
      >
        {_.map(this.props.value, this.renderInput)}
      </div>,
      this.renderDescription()
    ]);
  }
};

customControls.text_list = React.createClass({
  mixins: [multipleValuesInputMixin],
  renderInput(value, index) {
    var error = (this.props.error || [])[index] || null;
    return (
      <div
        key={'input' + index}
        className={utils.classNames({
          'has-error': !_.isNull(error)
        })}
      >
        <input
          {... _.pick(this.props, 'name', 'disabled')}
          ref={'input' + index}
          type='text'
          className='form-control'
          onChange={() => this.debouncedFieldChange(index)}
          defaultValue={value}
        />
        {this.renderMultipleInputControls(index)}
        {error &&
          <div className='help-block field-error'>{error}</div>
        }
      </div>
    );
  }
});

customControls.password_list = React.createClass({
  mixins: [multipleValuesInputMixin],
  getInitialState() {
    return {
      contentVisibilityMap: _.map(this.props.value, () => false)
    };
  },
  togglePassword(index) {
    var contentVisibilityMap = _.clone(this.state.contentVisibilityMap);
    contentVisibilityMap[index] = !contentVisibilityMap[index];
    this.setState({contentVisibilityMap});
  },
  renderInput(value, index) {
    var error = (this.props.error || [])[index] || null;
    return (
      <div
        key={'input' + index}
        className={utils.classNames({
          'input-group': true,
          'has-error': !_.isNull(error)
        })}
      >
        <input
          {... _.pick(this.props, 'name', 'disabled')}
          ref={'input' + index}
          type={this.state.contentVisibilityMap[index] ? 'text' : 'password'}
          className='form-control'
          onChange={() => this.debouncedFieldChange(index)}
          defaultValue={value}
        />
        <div className='input-group-addon' onClick={() => this.togglePassword(index)}>
          <i
            className={
              this.state.contentVisibilityMap[index] ?
              'glyphicon glyphicon-eye-close' : 'glyphicon glyphicon-eye-open'
            }
          />
        </div>
        {this.renderMultipleInputControls(index)}
        {error &&
          <div className='help-block field-error'>{error}</div>
        }
      </div>
    );
  }
});

customControls.textarea_list = React.createClass({
  mixins: [multipleValuesInputMixin],
  renderInput(value, index) {
    var error = (this.props.error || [])[index] || null;
    return (
      <div
        key={'input' + index}
        className={utils.classNames({'has-error': !_.isNull(error)})}
      >
        <textarea
          {... _.pick(this.props, 'name', 'disabled')}
          ref={'input' + index}
          className='form-control'
          onChange={() => this.debouncedFieldChange(index)}
          defaultValue={value}
        />
        {this.renderMultipleInputControls(index)}
        {error &&
          <div className='help-block field-error'>{error}</div>
        }
      </div>
    );
  }
});

customControls.file_list = React.createClass({
  mixins: [multipleValuesInputMixin],
  propTypes: {
    value: React.PropTypes.arrayOf(
        React.PropTypes.oneOfType([
          React.PropTypes.shape({
            name: React.PropTypes.string,
            content: React.PropTypes.string
          }),
          React.PropTypes.string
        ])
      ).isRequired
  },
  pickFile(index) {
    if (!this.props.disabled) ReactDOM.findDOMNode(this.refs['input' + index]).click();
  },
  saveFile(index, newValue) {
    var value = _.clone(this.props.value);
    value[index] = newValue;
    return this.props.onChange(this.props.name, value);
  },
  removeFile(index) {
    if (!this.props.disabled) {
      ReactDOM.findDOMNode(this.refs['form' + index]).reset();
      this.saveFile(index, {name: null, content: null});
    }
  },
  readFile(index) {
    var reader = new FileReader();
    var input = ReactDOM.findDOMNode(this.refs['input' + index]);
    if (input.files.length) {
      var fileName = input.value.replace(/^.*[\\\/]/g, '');
      reader.onload = () => this.saveFile(index, {name: fileName, content: reader.result});
      reader.readAsBinaryString(input.files[0]);
    }
  },
  renderInput(value, index) {
    var error = (this.props.error || [])[index] || null;
    return (
      <div
        key={'input' + index}
        className={utils.classNames({'has-error': !_.isNull(error)})}
      >
        <form ref={'form' + index}>
          <input
            {... _.pick(this.props, 'name', 'disabled')}
            ref={'input' + index}
            type='file'
            className='form-control'
            onChange={() => this.readFile(index)}
          />
        </form>
        <div className='input-group'>
          <input
            className='form-control file-name'
            type='text'
            placeholder={i18n('controls.file.placeholder')}
            value={value.name && ('[' + utils.showSize(value.content.length) + '] ' + value.name)}
            onClick={() => this.pickFile(index)}
            disabled={this.props.disabled}
            readOnly
          />
          <div
            className='input-group-addon'
            onClick={() => (value.name ? this.removeFile : this.pickFile)(index)}
          >
            <i
              className={value.name && !this.props.disabled ?
                'glyphicon glyphicon-remove' : 'glyphicon glyphicon-file'
              }
            />
          </div>
        </div>
        {this.renderMultipleInputControls(index)}
        {error &&
          <div className='help-block field-error'>{error}</div>
        }
      </div>
    );
  }
});

export default customControls;
