/*
 * Copyright 2016 Mirantis, Inc.
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
import {backboneMixin} from 'component_mixins';
import {Input} from 'views/controls';

var NFVComponent = React.createClass({
  mixins: [
    backboneMixin('nodeAttributes')
  ],
  onInputChange(name, value) {
    var {nodeAttributes} = this.props;
    var changesConfig = _.clone(nodeAttributes.toJSON());
    if (_.startsWith(name, 'dpdk')) {
      _.findWhere(changesConfig.dpdk_hugepages, {name: name}).value = value;
    }
    if (_.startsWith(name, 'nova')) {
      _.findWhere(changesConfig.nova_hugepages, {name: name}).value = value;
    }
    nodeAttributes.set(changesConfig);
    nodeAttributes.save();
  },
  render() {
    var commonInputProps = {
      placeholder: 'None',
      className: 'form-control',
      onChange: this.props.onNodeAttributesChange,
      error: null,
      type: 'text'
    };
    var {nodeAttributes} = this.props;
    if (!nodeAttributes) return null;
    var attributes = nodeAttributes.attributes;
    var sortedAttributes = _.sortBy(
      _.keys(attributes), (name) => nodeAttributes.get(name + '.metadata.weight')
    );
    var attributeFields = ['nova', 'dpdk'];
    return (
      <div className='nfv-component'>
        {_.map(sortedAttributes, (section) => {
          return _.map(attributeFields, (field) => {
            if (attributes[section][field].type === 'custom_hugepages') {
              return <NovaHugePages
                config={attributes[section][field]}
              />;
            }
            return (
              <div className='row'>
                <div className='col-xs-12'>
                  <Input
                    {...commonInputProps}
                    {...attributes[section][field]}
                    name={section + '.' + field}
                  />
                </div>
              </div>
            );
          });
        })}
        <button
          className='btn btn-success'
          onClick={this.props.saveNodeAttributes}
          >
          {i18n('common.save_settings_button')}
        </button>
      </div>
    );
  }
});

var NovaHugePages = React.createClass({
  render() {
    var inputProps = {
      placeholder: 'None',
      className: 'form-control',
      onChange: this.props.onNodeAttributesChange,
      error: null,
      description: null,
      type: 'text'
    };
    return (
      <div className='row huge-pages'>
        <div className='col-xs-12'>
          <label>
            <span>{'Nova Huge pages'}</span>
          </label>
        </div>
        <div className='row labels'>
          <div className='col-xs-1'>
            <span>{'Size'}</span>
          </div>
          <div className='col-xs-11'>
            <span>{'Count'}</span>
          </div>
        </div>
        <div className='contents'>
          {_.map(
            _.isEmpty(this.props.config.value) ? {'0M': 0} : this.props.config.value,
              (value, name) => {
                return (
                  <div className='row' key={name}>
                    <div className='col-xs-1'>
                      <p>
                        {name}
                      </p>
                    </div>
                    <div className='col-xs-11'>
                      <Input
                        {...inputProps}
                        value={value}
                        key={value}
                        name='custom_hugepages'
                      />
                    </div>
                  </div>
                );
              }
          )}
        </div>
      </div>
    );
  }
});

export default NFVComponent;
