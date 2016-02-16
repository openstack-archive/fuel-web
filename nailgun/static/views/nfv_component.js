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
//import i18n from 'i18n';
import React from 'react';
import models from 'models';
import {backboneMixin} from 'component_mixins';
import {Input} from 'views/controls';

var NFVComponent = React.createClass({
  mixins: [
    backboneMixin('node')
  ],
  componentWillReceiveProps() {
    this.nodeAttributes = new models.NodeAttributes({
      url: '/api/nodes/' + this.props.node.id + '/attributes'
    });
    //@TODO: fetch model
  },
  componentDidMount() {
    this.nodeAttributes = new models.NodeAttributes();
    this.nodeAttributes.url = '/api/nodes/' + this.props.node.id + '/attributes';
  },
  onInputChange(name, value) {
    var node = this.props.node;
    var changesConfig = _.clone(node.get('meta').nfv_attributes);
    if (_.startsWith(name, 'dpdk')) {
      _.findWhere(changesConfig.dpdk_hugepages, {name: name}).value = value;
    }
    if (_.startsWith(name, 'nova')) {
      _.findWhere(changesConfig.nova_hugepages, {name: name}).value = value;
    }
    node.save();
    this.nodeAttributes.set(changesConfig);
    this.nodeAttributes.save();
  },
  render() {
    var commonInputProps = {
      placeholder: 'None',
      className: 'form-control',
      onChange: this.onInputChange,
      error: null
    };
    var unitedConfig = _.union(this.props.config.dpdk_hugepages, this.props.config.nova_hugepages);
    return (
      <div className='panel-body enable-selection nfv-component'>
        {_.map(unitedConfig, (elementConfig) => {
          if (elementConfig.type === 'custom_hugepages') {
            return (
              <NovaHugePages
                config={elementConfig}
                key={'custom_hugepages'}
              />
            );
          }
          return (
            <div className='row' key={elementConfig.name}>
              <div className='col-xs-12'>
                <Input
                  {...commonInputProps}
                  {...elementConfig}
                  key={name}
                />
              </div>
            </div>
          );
        })}
      </div>
    );
  }
});

var NovaHugePages = React.createClass({
  render() {
    var inputProps = {
      placeholder: 'None',
      className: 'form-control',
      onChange: this.onInputChange,
      error: null,
      description: null,
      type: 'text'
    };

    var config = this.props.config;
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
          {_.map(config.value, (value, name) => {
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
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }
});

export default NFVComponent;
