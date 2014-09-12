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
define(['jquery', 'underscore', 'react'], function($, _, React) {
    'use strict';

    var controls = {},
        cx = React.addons.classSet;

    var tooltipMixin = {
        componentDidMount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip();
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
            // props used by <input />
            type: React.PropTypes.string.isRequired,
            name: React.PropTypes.string,
            defaultValue: React.PropTypes.oneOfType([
                React.PropTypes.string,
                React.PropTypes.number,
                React.PropTypes.bool
            ]),
            defaultChecked: React.PropTypes.bool,
            disabled: React.PropTypes.bool,
            onChange: React.PropTypes.func,
            onKeyDown: React.PropTypes.func,
            maxLength: React.PropTypes.renderable,
            label: React.PropTypes.renderable,
            description: React.PropTypes.renderable,
            commonClassName: React.PropTypes.renderable,
            labelClassName: React.PropTypes.renderable,
            descriptionClassName: React.PropTypes.renderable,
            inputClassName: React.PropTypes.string,
            tooltipText: React.PropTypes.renderable,
            toggleable: React.PropTypes.bool,
            validate: React.PropTypes.func
        },
        getInitialState: function() {
            return {visible: false};
        },
        getError: function() {
            var validationResult  = this.props.validate && this.props.validate(this.props.name);
            if (_.isBoolean(validationResult)) {
                return {
                    result: validationResult,
                    message: ''
                };
            }
            return validationResult;
        },
        togglePassword: function() {
            if (this.props.disabled) return;
            this.setState({visible: !this.state.visible});
        },
        isCheckboxOrRadio: function() {
            return this.props.type === 'radio' || this.props.type === 'checkbox';
        },
        getValue: function() {
            var input = this.refs.input.getDOMNode();
            return this.isCheckboxOrRadio() ? input.checked : input.value;
        },
        renderInput: function() {
            var input = null,
                className = cx({
                    'parameter-input': this.isCheckboxOrRadio(),
                    error: this.getError().result
                });
            switch (this.props.type) {
                case 'dropdown':
                    input = (<select ref='input' key='input' className={className}>{this.props.children}</select>);
                    break;
                case 'textarea':
                    input = <textarea ref='input' key='input' className={className} />;
                    break;
                case 'password':
                    var type = (this.props.toggleable && this.state.visible) ? 'text' : 'password';
                    input = <input ref='input' key='input' className={className} type={type} />;
                    break;
                default:
                    input = <input ref='input' key='input' className={className} />;
            }
            return this.isCheckboxOrRadio() ? (
                <div key='input-wrapper' className='custom-tumbler'>
                    {this.transferPropsTo(input)}
                    <span>&nbsp;</span>
                </div>
            ) : this.props.toggleable ?
                input
                : this.transferPropsTo(input);
        },
        renderToggleablePasswordAddon: function() {
            return this.props.toggleable ? (
                <span key='add-on' className='add-on' onClick={this.togglePassword}>
                    <i className={this.state.visible ? 'icon-eye-off' : 'icon-eye'} />
                </span>
            ) : null;
        },
        renderInputLabel: function() {
            var classes = {
                'parameter-name enable-selection': true
            };
            classes[this.props.labelClassName] = this.props.labelClassName;
            return (
                <div className={cx(classes)}>
                    <span>{this.props.label}</span>
                </div>
            );
        },
        renderLabel: function(children) {
            var classes = {
                'parameter-name enable-selection': true,
                'input-append': this.props.toggleable
            };
            classes[this.props.labelClassName] = this.props.labelClassName;
            return this.props.label ? (
                <label key='label' className={cx(classes)} htmlFor={this.props.id}>
                    <div className='label-wrapper'>{this.props.label}</div>
                    {children}
                </label>
            ) : children;
        },
        renderDescription: function() {
            var error =  this.getError(),
                hasError = !_.isNull(this.props.error) || error.result,
                classes = {'parameter-description enable-selection': true,
                    'validation-error': hasError};
            classes[this.props.descriptionClassName] = this.props.descriptionClassName;
            return hasError || this.props.description ? (
                <div key='description' className={cx(classes)}>
                    {hasError ? this.props.error || error.message : this.props.description}
                </div>
            ) : null;
        },
        renderWrapper: function(children) {
            var classes = {
                'parameter-box': true,
                clearfix: !this.isCheckboxOrRadio(),
                'has-error': !_.isNull(this.props.error) && !_.isUndefined(this.props.error)
            };
            classes[this.props.commonClassName] = this.props.commonClassName;
            return (<div className={cx(classes)}>{children}</div>);
        },
        renderParameterControl: function(children) {
            var classes = {
                'parameter-control': true,
                'input-append': this.props.toggleable
            };
            return (<div className={cx(classes)}>{children}</div>);
        },
        render: function() {
            if (this.isCheckboxOrRadio()) {
                return this.renderWrapper([
                    this.renderLabel([
                        this.renderInput(),
                        this.renderTooltipIcon()
                    ]),
                    this.renderDescription()
                ]);
            } else {
                return this.renderWrapper([
                    this.renderInputLabel(),
                    this.renderParameterControl([
                        this.renderInput(),
                        this.renderToggleablePasswordAddon()
                    ]),
                    this.renderDescription()
                ]);
            }
        }
    });

    controls.RadioGroup = React.createClass({
        mixins: [tooltipMixin],
        propTypes: {
            name: React.PropTypes.string,
            values: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            label: React.PropTypes.renderable,
            labelClassName: React.PropTypes.renderable,
            tooltipText: React.PropTypes.renderable
        },
        render: function() {
            var labelClasses = {'parameter-name': true};
            labelClasses[this.props.labelClassName] = this.props.labelClassName;
            return (
                <div>
                    {this.props.label &&
                        <label className={cx(labelClasses)}>
                            <div className='label-wrapper'>{this.props.label}</div>
                            {this.renderTooltipIcon()}
                        </label>
                    }
                    {_.map(this.props.values, function(value) {
                        return this.transferPropsTo(
                            <controls.Input
                                key={value.data}
                                type='radio'
                                value={value.data}
                                defaultChecked={value.checked}
                                label={value.label}
                                description={value.description}
                                disabled={value.disabled}
                                tooltipText={value.tooltipText}
                            />
                        );
                    }, this)}
                </div>
            );
        }
    });

    controls.SelectAllCheckbox = React.createClass({
        render: function() {
            return this.transferPropsTo(<controls.Input type='checkbox' label={$.t('common.select_all')} commonClassName='select-all' />);
        }
    });

    controls.ProgressBar = React.createClass({
        render: function() {
            return (
                <div className='progress-bar'>
                    <div className='progress progress-striped progress-success active'>
                        <div className='bar'/>
                    </div>
                </div>
            );
        }
    });

    controls.Table = React.createClass({
        render: function() {
            var tableClasses = {'table table-bordered table-striped': true};
            tableClasses[this.props.tableClassName] = this.props.tableClassName;
            return (
                <table className={cx(tableClasses)}>
                    <thead>
                        <tr>
                            {_.map(this.props.head, function(column, index) {
                                return <th key={index} className={column.className || ''}>{column.label}</th>;
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

    return controls;
});
