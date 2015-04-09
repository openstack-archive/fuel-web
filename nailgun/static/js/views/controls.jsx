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

define([
    'jquery',
    'underscore',
    'react',
    'react-sticky',
    'utils',
    'jsx!component_mixins'
], function($, _, React, Sticky, utils, componentMixins) {
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
                <i key='tooltip' ref='tooltip' className='icon-attention text-warning' data-toggle='tooltip' title={this.props.tooltipText} />
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
            labelClassName: React.PropTypes.node,
            labelWrapperClassName: React.PropTypes.node,
            descriptionClassName: React.PropTypes.node,
            wrapperClassName: React.PropTypes.node,
            tooltipText: React.PropTypes.node,
            toggleable: React.PropTypes.bool,
            labelBeforeControl: React.PropTypes.bool,
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
            var classes = {
                'parameter-input': true,
                'input-append': this.props.toggleable
            };
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
                inputWrapperClasses = {'input-wrapper': this.props.type != 'hidden', 'custom-tumbler': isCheckboxOrRadio};
            return (
                <div key='input-wrapper' className={utils.classNames(inputWrapperClasses)}>
                    {input}
                    {isCheckboxOrRadio && <span>&nbsp;</span>}
                    {this.props.extraContent}
                </div>
            );
        },
        renderToggleablePasswordAddon: function() {
            return this.props.toggleable ? (
                <span key='add-on' className='add-on' onClick={this.togglePassword}>
                    <i className={this.state.visible ? 'icon-eye-off' : 'icon-eye'} />
                </span>
            ) : null;
        },
        renderLabel: function(children) {
            var labelClasses = {
                    'parameter-name': true,
                    'input-append': this.props.toggleable
                },
                labelWrapperClasses = {
                    'label-wrapper': true
                };

            labelClasses[this.props.labelClassName] = this.props.labelClassName;
            labelWrapperClasses[this.props.labelWrapperClassName] = this.props.labelWrapperClassName;
            var labelElement = (
                    <div className={utils.classNames(labelWrapperClasses)}>
                        <span>{this.props.label}</span>
                        {this.renderTooltipIcon()}
                    </div>
                ),
                labelBefore = (!this.isCheckboxOrRadio() || this.props.labelBeforeControl) ? labelElement : null,
                labelAfter = (this.isCheckboxOrRadio() && !this.props.labelBeforeControl) ? labelElement : null;
            return this.props.label ? (
                <label key='label' className={utils.classNames(labelClasses)} htmlFor={this.props.id}>
                    {labelBefore}
                    {children}
                    {labelAfter}
                </label>
            )
            : children;
        },
        renderDescription: function() {
            var error = !_.isUndefined(this.props.error) && !_.isNull(this.props.error),
                classes = {'parameter-description': true};
            classes[this.props.descriptionClassName] = this.props.descriptionClassName;
            return error || this.props.description ? (
                <div key='description' className={utils.classNames(classes)}>
                    {error ?
                        this.props.error :
                        this.props.description.split('\n').map(function(line, index) {
                                return <p key={index}>{line}</p>;
                            }
                        )
                    }
                </div>
            ) : null;
        },
        renderWrapper: function(children) {
            var isCheckboxOrRadio = this.isCheckboxOrRadio(),
                classes = {
                    'parameter-box': true,
                    'checkbox-or-radio': isCheckboxOrRadio,
                    clearfix: !isCheckboxOrRadio,
                    'has-error': !_.isUndefined(this.props.error) && !_.isNull(this.props.error),
                    disabled: this.props.disabled
                };
            classes[this.props.wrapperClassName] = this.props.wrapperClassName;
            return (<div className={utils.classNames(classes)}>{children}</div>);
        },
        render: function() {
            return this.renderWrapper([
                this.renderLabel([
                    this.renderInput(),
                    this.renderToggleablePasswordAddon()
                ]),
                this.renderDescription()
            ]);
        }
    });

    controls.RadioGroup = React.createClass({
        mixins: [tooltipMixin],
        propTypes: {
            name: React.PropTypes.string,
            values: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            label: React.PropTypes.node,
            labelClassName: React.PropTypes.node,
            tooltipText: React.PropTypes.node
        },
        render: function() {
            var labelClasses = {'parameter-name': true};
            labelClasses[this.props.labelClassName] = this.props.labelClassName;
            return (
                <div className='radio-group'>
                    {this.props.label &&
                        <label className={utils.classNames(labelClasses)}>
                            {this.props.label}
                            {this.renderTooltipIcon()}
                            <hr />
                        </label>
                    }
                    {_.map(this.props.values, function(value) {
                        return <controls.Input {...this.props}
                            key={value.data}
                            type='radio'
                            value={value.data}
                            defaultChecked={value.defaultChecked}
                            checked={value.checked}
                            label={value.label}
                            description={value.description}
                            disabled={value.disabled}
                            tooltipText={value.tooltipText}
                        />;
                    }, this)}
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
            placement: React.PropTypes.node
        },
        getDefaultProps: function() {
            return {placement: 'bottom'};
        },
        render: function() {
            var classes = {'popover in': true};
            classes[this.props.placement] = true;
            classes[this.props.className] = true;
            return (
                <div className={utils.classNames(classes)}>
                    <div className='arrow' />
                    <div className='popover-content'>{this.props.children}</div>
                </div>
           );
        }
    });

    controls.StickyControls = React.createClass({
        propTypes: {
            buttons: React.PropTypes.arrayOf(React.PropTypes.object)
        },
        composeButtonClasses: function(data) {
            var classes = {btn: true, 'btn-default': !data.className};
            classes['btn-' + data.key] = true;
            classes[data.className] = data.className;
            return classes;
        },
        render: function() {
            return (
                <Sticky>
                    <div className='row'>
                        <div id='sticker'>
                            <div className='col-xs-12'>
                                {this.props.children}
                                {this.props.buttons &&
                                    <div className='control-buttons-box pull-right'>
                                        {this.props.buttons.map(function(data) {
                                            return (
                                                <button
                                                    key={data.key}
                                                    className={utils.classNames(this.composeButtonClasses(data))}
                                                    onClick={data.onClick}
                                                    disabled={data.disabled}
                                                >
                                                    {data.iconClassName && <i className={data.iconClassName} />}
                                                    {data.title}
                                                </button>
                                            );
                                        }, this)}
                                    </div>
                                }
                            </div>
                        </div>
                    </div>
                </Sticky>
            );
        }
    });

    return controls;
});
