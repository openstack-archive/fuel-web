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

define(['jquery', 'underscore', 'react'], function($, _, React) {
    'use strict';

    var controls = {},
        cx = React.addons.classSet;

    var tooltipMixin = {
        componentDidMount: function() {
            if (this.props.tooltipText) $(this.refs.tooltip.getDOMNode()).tooltip();
        },
        componentDidUpdate: function() {
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
            type: React.PropTypes.string.isRequired,
            name: React.PropTypes.string,
            label: React.PropTypes.renderable,
            description: React.PropTypes.renderable,
            disabled: React.PropTypes.bool,
            wrapperClassName: React.PropTypes.renderable,
            labelClassName: React.PropTypes.renderable,
            descriptionClassName: React.PropTypes.renderable,
            labelWrapperClassName:  React.PropTypes.renderable,
            inputClassName: React.PropTypes.renderable,
            tooltipText: React.PropTypes.renderable,
            toggleable: React.PropTypes.bool
        },
        getInitialState: function() {
            return {visible: false};
        },
        togglePassword: function() {
            if (this.props.disabled) return;
            this.setState({visible: !this.state.visible});
        },
        isCheckboxOrRadio: function() {
            return this.props.type == 'radio' || this.props.type == 'checkbox';
        },
        onChange: function() {
            var input = this.refs.input.getDOMNode();
            return this.props.onChange(this.props.name, this.props.type == 'checkbox' ? input.checked : input.value);
        },
        renderInput: function() {
            var input = null,
                className = {'parameter-input': true};
            className[this.props.inputClassName] = this.props.inputClassName;
            switch (this.props.type) {
                case 'select':
                    input = (<select ref='input' key='input' className={cx(className)} onChange={this.onChange}>{this.props.children}</select>);
                    break;
                case 'textarea':
                    input = <textarea ref='input' key='input' className={cx(className)} onChange={this.onChange} />;
                    break;
                case 'password':
                    var type = (this.props.toggleable && this.state.visible) ? 'text' : 'password';
                    input = <input ref='input' key='input' className={cx(className)} type={type} onChange={this.onChange} />;
                    break;
                default:
                    input = <input ref='input' key='input' className={cx(className)} onChange={this.onChange} value={this.props.value} />;
            }
            return this.isCheckboxOrRadio() ? (
                <div key='input-wrapper' className='custom-tumbler'>
                    {this.transferPropsTo(input)}
                    <span>&nbsp;</span>
                </div>
            ) : this.transferPropsTo(input);
        },
        renderToggleablePasswordAddon: function() {
            return this.props.toggleable ? (
                <span key='add-on' className='add-on' onClick={this.togglePassword}>
                    <i className={this.state.visible ? 'icon-eye-off' : 'icon-eye'} />
                </span>
            ) : null;
        },
        renderLabel: function(children) {
            var classes = {
                'parameter-name': true,
                'input-append': this.props.toggleable
            };
            classes[this.props.labelClassName] = this.props.labelClassName;
            var labelWrapperClasses = {
                'label-wrapper enable-selection': true
            };
            labelWrapperClasses[this.props.labelWrapperClassName] = this.props.labelWrapperClassName;
            return this.props.label ? (
                <label key='label' className={cx(classes)} htmlFor={this.props.id}>
                    {(!this.isCheckboxOrRadio() || this.props.labelBeforeControl) &&
                        <div className='input-label enable-selection'>
                            <span>{this.props.label}</span>
                            {this.renderTooltipIcon()}
                        </div>
                    }
                    {children}
                    {(this.isCheckboxOrRadio() && !this.props.labelBeforeControl) &&
                        <div className={cx(labelWrapperClasses)}>
                            {this.props.label}
                            {this.renderTooltipIcon()}
                        </div>
                    }
                </label>
            )
            : this.props.title ? (
                <div key={this.props.title}>
                    <div className='parameter-name'>{this.props.title}</div>
                    {children}
                </div>
                )
            : children;
        },
        renderDescription: function() {
            var error = !_.isUndefined(this.props.error) && !_.isNull(this.props.error),
                classes = {'parameter-description enable-selection': true};
            classes[this.props.descriptionClassName] = this.props.descriptionClassName;
            return error || this.props.description ? (
                <div key='description' className={cx(classes)}>
                    {error ? this.props.error : this.props.description}
                </div>
            ) : null;
        },
        renderWrapper: function(children) {
            var classes = {
                'parameter-box': true,
                clearfix: !this.isCheckboxOrRadio(),
                'has-error': !_.isUndefined(this.props.error) && !_.isNull(this.props.error)
            };
            classes[this.props.wrapperClassName] = this.props.wrapperClassName;
            return (<div className={cx(classes)}>{children}</div>);
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
            label: React.PropTypes.renderable,
            labelClassName: React.PropTypes.renderable,
            tooltipText: React.PropTypes.renderable
        },
        render: function() {
            var labelClasses = {'parameter-name': true};
            labelClasses[this.props.labelClassName] = this.props.labelClassName;
            return (
                <div className='radio-group'>
                    {this.props.label &&
                        <label className={cx(labelClasses)}>
                            {this.props.label}
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
        propTypes: {
            tableClassName: React.PropTypes.renderable,
            head: React.PropTypes.array,
            body: React.PropTypes.array
        },
        render: function() {
            var tableClasses = this.props.noStripes ? {} : {'table table-bordered table-striped': true};
            tableClasses[this.props.tableClassName] = this.props.tableClassName;
            return (
                <table className={cx(tableClasses)}>
                    <thead>
                        <tr>
                            {_.map(this.props.head, function(column, index) {
                                var classes = {};
                                classes[column.className] = column.className;
                                return <th key={index} className={cx(classes)}>{column.label}</th>;
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
