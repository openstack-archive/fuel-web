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

/*
 * Copyright (с) 2014 Stephen J. Collings, Matthew Honnibal, Pieter Vanderwerff
 *
 * Based on https://github.com/react-bootstrap/react-bootstrap/blob/master/src/Input.jsx
**/

define(['jquery', 'underscore', 'react', 'utils', 'jsx!component_mixins'], function($, _, React, utils, componentMixins) {
    'use strict';

    var controls = {};

    var tooltipMixin = controls.tooltipMixin = {
        componentDidMount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip();
        },
        componentDidUpdate: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip('destroy').tooltip();
        },
        componentWillUnmount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip('destroy');
        },
        renderTooltipIcon: function() {
            return this.props.tooltipText ? (
                <i
                    key='tooltip'
                    ref='tooltip'
                    className='glyphicon glyphicon-warning-sign tooltip-icon'
                    data-toggle='tooltip'
                    data-placement='right'
                    title={this.props.tooltipText}
                />
            ) : null;
        }
    };

    controls.Input = React.createClass({
        mixins: [tooltipMixin],
        propTypes: {
            type: React.PropTypes.oneOf(['text', 'password', 'textarea', 'checkbox', 'radio', 'select', 'hidden', 'number']).isRequired,
            name: React.PropTypes.node,
            label: React.PropTypes.node,
            description: React.PropTypes.node,
            disabled: React.PropTypes.bool,
            inputClassName: React.PropTypes.node,
            wrapperClassName: React.PropTypes.node,
            tooltipText: React.PropTypes.node,
            toggleable: React.PropTypes.bool,
            onChange: React.PropTypes.func,
            extraContent: React.PropTypes.node
        },
        getInitialState: function() {
            return {visible: false};
        },
        togglePassword: function() {
            this.setState({visible: !this.state.visible});
        },
        isCheckboxOrRadio: function() {
            return this.props.type == 'radio' || this.props.type == 'checkbox';
        },
        getInputDOMNode: function() {
            return this.refs.input.getDOMNode();
        },
        debouncedChange: _.debounce(function() {
            return this.onChange();
        }, 200, {leading: true}),
        onChange: function() {
            if (this.props.onChange) {
                var input = this.getInputDOMNode();
                return this.props.onChange(this.props.name, this.props.type == 'checkbox' ? input.checked : input.value);
            }
        },
        renderInput: function() {
            var classes = {'form-control': true};
            classes[this.props.inputClassName] = this.props.inputClassName;
            var props = {
                    ref: 'input',
                    key: 'input',
                    type: (this.props.toggleable && this.state.visible) ? 'text' : this.props.type,
                    className: utils.classNames(classes),
                    // debounced onChange callback is supported for uncontrolled inputs
                    onChange: this.props.value ? this.onChange : this.debouncedChange
                },
                Tag = _.contains(['select', 'textarea'], this.props.type) ? this.props.type : 'input',
                input = <Tag {...this.props} {...props}>{this.props.children}</Tag>,
                isCheckboxOrRadio = this.isCheckboxOrRadio(),
                inputWrapperClasses = {
                    'input-group': this.props.toggleable,
                    'custom-tumbler': isCheckboxOrRadio,
                    textarea: this.props.type == 'textarea'
                };
            return (
                <div key='input-group' className={utils.classNames(inputWrapperClasses)}>
                    {input}
                    {this.props.toggleable &&
                        <div className='input-group-addon' onClick={this.togglePassword}>
                            <i className={this.state.visible ? 'glyphicon glyphicon-eye-close' : 'glyphicon glyphicon-eye-open'} />
                        </div>
                    }
                    {isCheckboxOrRadio && <span>&nbsp;</span>}
                    {this.props.extraContent}
                </div>
            );
        },
        renderLabel: function(children) {
            return (
                <label key='label' htmlFor={this.props.id}>
                    {children}
                    {this.props.label}
                    {this.renderTooltipIcon()}
                </label>
            );
        },
        renderDescription: function() {
            return (
                <span key='description' className='help-block'>
                    {!_.isUndefined(this.props.error) && !_.isNull(this.props.error) ?
                        this.props.error :
                        this.props.description && this.props.description.split('\n').map(function(line, index) {
                                return <p key={index}>{line}</p>;
                            }
                        )
                    }
                </span>
            );
        },
        renderWrapper: function(children) {
            var isCheckboxOrRadio = this.isCheckboxOrRadio(),
                classes = {
                    'form-group': !isCheckboxOrRadio,
                    'checkbox-group': isCheckboxOrRadio,
                    'has-error': !_.isUndefined(this.props.error) && !_.isNull(this.props.error),
                    disabled: this.props.disabled
                };
            classes[this.props.wrapperClassName] = this.props.wrapperClassName;
            return (<div className={utils.classNames(classes)}>{children}</div>);
        },
        render: function() {
            return this.renderWrapper(this.isCheckboxOrRadio() ?
                [
                    this.renderLabel(this.renderInput()),
                    this.renderDescription()
                ] : [
                    this.renderLabel(),
                    this.renderInput(),
                    this.renderDescription()
                ]
            );
        }
    });

    controls.RadioGroup = React.createClass({
        mixins: [tooltipMixin],
        propTypes: {
            name: React.PropTypes.string,
            values: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            label: React.PropTypes.node,
            tooltipText: React.PropTypes.node,
            disabled: React.PropTypes.bool
        },
        render: function() {
            return (
                <div className='radio-group'>
                    {this.props.label &&
                        <h4>
                            {this.props.label}
                            {this.renderTooltipIcon()}
                        </h4>
                    }
                    {_.map(this.props.values, function(value) {
                        return <controls.Input
                            {...this.props}
                            {...value}
                            type='radio'
                            key={value.data}
                            value={value.data}
                        />;
                    }, this)}
                </div>
            );
        }
    });

    controls.MultiSelect = React.createClass({
        propTypes: {
            name: React.PropTypes.string,
            options: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            label: React.PropTypes.node.isRequired,
            disabled: React.PropTypes.bool,
            simple: React.PropTypes.bool,
            onChange: React.PropTypes.func,
            extraContent: React.PropTypes.node,
            sort: React.PropTypes.bool
        },
        getInitialState: function() {
            return {
                itemsVisible: false,
                values: this.props.values || []
            };
        },
        toggle: function(visible) {
            this.setState({
                itemsVisible: _.isBoolean(visible) ? visible : !this.state.itemsVisible
            });
        },
        onChange: function(name, checked) {
            var values = name == 'all' ?
                    checked ? _.pluck(this.props.options, 'name') : []
                :
                    checked ? _.union(this.state.values, [name]) : _.difference(this.state.values, [name]);
            this.setState({values: values});
        },
        render: function() {
            var controlClasses = {
                    'btn-group multiselect': true,
                    open: this.state.itemsVisible
                },
                buttonClasses = {
                    'btn dropdown-toggle': true,
                    'btn-link': this.props.simple && !this.state.itemsVisible,
                    'btn-default': !(this.props.simple && !this.state.itemsVisible)
                };

            var label = !this.props.simple && this.state.values.length ?
                    this.state.values.length > 3 ? this.state.values.length + ' selected' : _.map(this.state.values, function(itemName) {
                        return _.find(this.props.options, {name: itemName}).label;
                    }, this).join(', ')
                :
                    this.props.label;

            if (this.props.sort) {
                this.props.options.sort(function(option1, option2) {
                    return utils.natsort(option1.label, option2.label);
                });
            }

            return (
                <div className={utils.classNames(controlClasses)}>
                    <button className={utils.classNames(buttonClasses)} onClick={this.toggle} disabled={this.props.disabled}>
                        {label} <span className='caret'></span>
                    </button>
                    {this.state.itemsVisible &&
                        <controls.Popover toggle={this.toggle} showArrow={false}>
                            {!this.props.simple && [
                                    <div key='all'>
                                        <controls.Input
                                            type='checkbox'
                                            label='Select All'
                                            name='all'
                                            checked={this.state.values.length == this.props.options.length}
                                            onChange={this.props.onChange || this.onChange}
                                        />
                                    </div>,
                                    <div key='divider' className='divider' />
                                ]
                            }
                            {_.map(this.props.options, function(option, index) {
                                return (
                                    <controls.Input {...option}
                                        key={index}
                                        type='checkbox'
                                        checked={_.contains(this.state.values, option.name)}
                                        onChange={this.props.onChange || this.onChange}
                                    />
                                );
                            }, this)}
                        </controls.Popover>
                    }
                    {this.props.extraContent}
                </div>
            );
        }
    });

    controls.NumberRange = React.createClass({
        mixins: [componentMixins.outerClickMixin],
        propTypes: {
            name: React.PropTypes.string,
            disabled: React.PropTypes.bool,
            onChange: React.PropTypes.func,
            prefix: React.PropTypes.string,
            extraContent: React.PropTypes.node
        },
        getInitialState: function() {
            return {
                itemsVisible: false,
                values: []
            };
        },
        toggle: function(visible) {
            this.setState({
                itemsVisible: _.isBoolean(visible) ? visible : !this.state.itemsVisible
            });
        },
        onChange: function(name, value) {
            value = value == '' ? undefined : Number(value);
            if (!_.isNaN(value)) {
                var values = this.state.values;
                if (_.contains(name, 'start')) {
                    values[0] = value;
                } else {
                    values[0] = values[0] || 0;
                    values[1] = value;
                }
                this.setState({values: values});
            }
        },
        render: function() {
            var values = this.state.values;
            var controlClasses = {
                    'btn-group number-range': true,
                    open: this.state.itemsVisible
                };

            var props = {
                    type: 'number',
                    disabled: this.props.disabled,
                    onChange: this.props.onChange || this.onChange,
                    inputClassName: 'pull-left',
                    error: values[0] > values[1] || null
                };

            var label = _.all(values, _.isUndefined) ?
                    this.props.label
                :
                    (
                        !_.isUndefined(values[0]) && !_.isUndefined(values[1]) ?
                            values[0] == values[1] ? values[0] : values[0] + ' - ' + values[1]
                        :
                            !_.isUndefined(values[0]) ? 'More than ' + values[0] : 'Less than ' + values[1]
                    ) + ' ' + this.props.prefix;

            return (
                <div className={utils.classNames(controlClasses)}>
                    <button className='btn btn-default dropdown-toggle' disabled={this.props.disabled} onClick={this.toggle}>
                        {label} <span className='caret'></span>
                    </button>
                    {this.state.itemsVisible &&
                        <controls.Popover toggle={this.toggle} showArrow={false}>
                            <div className='clearfix'>
                                <controls.Input {...props}
                                    name={this.props.name + '-start'}
                                    value={values[0]}
                                />
                                <span className='pull-left'> &mdash; </span>
                                <controls.Input {...props}
                                    name={this.props.name + '-end'}
                                    value={values[1]}
                                />
                            </div>
                        </controls.Popover>
                    }
                    {this.props.extraContent}
                </div>
            );
        }
    });

    controls.ProgressBar = React.createClass({
        render: function() {
            return (
                <div className='progress'>
                    <div className='progress-bar progress-bar-striped active' style={{width: '100%'}}></div>
                </div>
            );
        }
    });

    controls.Table = React.createClass({
        propTypes: {
            tableClassName: React.PropTypes.node,
            head: React.PropTypes.array,
            body: React.PropTypes.array
        },
        render: function() {
            var tableClasses = {'table table-bordered': true, 'table-striped': !this.props.noStripes};
            tableClasses[this.props.tableClassName] = this.props.tableClassName;
            return (
                <table className={utils.classNames(tableClasses)}>
                    <thead>
                        <tr>
                            {_.map(this.props.head, function(column, index) {
                                var classes = {};
                                classes[column.className] = column.className;
                                return <th key={index} className={utils.classNames(classes)}>{column.label}</th>;
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {_.map(this.props.body, function(row, rowIndex) {
                            return <tr key={rowIndex}>
                                {_.map(row, function(column, columnIndex) {
                                    return <td key={columnIndex} className='enable-selection'>{column}</td>;
                                })}
                            </tr>;
                        })}
                    </tbody>
                </table>
            );
        }
    });

    controls.Popover = React.createClass({
        mixins: [componentMixins.outerClickMixin],
        propTypes: {
            className: React.PropTypes.node,
            placement: React.PropTypes.node,
            showArrow: React.PropTypes.bool
        },
        getDefaultProps: function() {
            return {
                placement: 'bottom',
                showArrow: true
            };
        },
        render: function() {
            var classes = {'popover in': true};
            classes[this.props.placement] = true;
            classes[this.props.className] = true;
            return (
                <div className={utils.classNames(classes)}>
                    {this.props.showArrow && <div className='arrow' />}
                    <div className='popover-content'>{this.props.children}</div>
                </div>
            );
        }
    });

    return controls;
});
