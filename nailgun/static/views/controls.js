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

define(['i18n', 'jquery', 'underscore', 'react', 'react-dom', 'utils', 'component_mixins'],
    function(i18n, $, _, React, ReactDOM, utils, componentMixins) {
    'use strict';

    var controls = {};

    controls.Input = React.createClass({
        propTypes: {
            type: React.PropTypes.oneOf(['text', 'password', 'textarea', 'checkbox', 'radio', 'select', 'hidden', 'number', 'range', 'file']).isRequired,
            name: React.PropTypes.node,
            label: React.PropTypes.node,
            debounce: React.PropTypes.bool,
            description: React.PropTypes.node,
            disabled: React.PropTypes.bool,
            inputClassName: React.PropTypes.node,
            wrapperClassName: React.PropTypes.node,
            tooltipPlacement: React.PropTypes.oneOf(['left', 'right', 'top', 'bottom']),
            tooltipIcon: React.PropTypes.node,
            tooltipText: React.PropTypes.node,
            toggleable: React.PropTypes.bool,
            onChange: React.PropTypes.func,
            extraContent: React.PropTypes.node
        },
        getInitialState() {
            return {
                visible: false,
                fileName: this.props.defaultValue && this.props.defaultValue.name || null,
                content: this.props.defaultValue && this.props.defaultValue.content || null
            };
        },
        getDefaultProps() {
            return {
                tooltipIcon: 'glyphicon-warning-sign',
                tooltipPlacement: 'right'
            };
        },
        togglePassword() {
            this.setState({visible: !this.state.visible});
        },
        isCheckboxOrRadio() {
            return this.props.type == 'radio' || this.props.type == 'checkbox';
        },
        getInputDOMNode() {
            return ReactDOM.findDOMNode(this.refs.input);
        },
        debouncedChange: _.debounce(function() {
            return this.onChange();
        }, 200, {leading: true}),
        pickFile() {
            if (!this.props.disabled) {
                this.getInputDOMNode().click();
            }
        },
        saveFile(fileName, content) {
            this.setState({
                fileName: fileName,
                content: content
            });
            return this.props.onChange(
                this.props.name,
                {name: fileName, content: content}
            );
        },
        removeFile() {
            if (!this.props.disabled) {
                ReactDOM.findDOMNode(this.refs.form).reset();
                this.saveFile(null, null);
            }
        },
        readFile() {
            var reader = new FileReader(),
                input = this.getInputDOMNode();

            if (input.files.length) {
                reader.onload = (function() {
                    return this.saveFile(input.value.replace(/^.*[\\\/]/g, ''), reader.result);
                }).bind(this);
                reader.readAsBinaryString(input.files[0]);
            }
        },
        onChange() {
            if (this.props.onChange) {
                var input = this.getInputDOMNode();
                return this.props.onChange(
                    this.props.name,
                    this.props.type == 'checkbox' ? input.checked : input.value
                );
            }
        },
        handleFocus(e) {
            e.target.select();
        },
        renderInput() {
            var classes = {'form-control': this.props.type != 'range'};
            classes[this.props.inputClassName] = this.props.inputClassName;
            var props = {
                ref: 'input',
                key: 'input',
                onFocus: this.props.selectOnFocus && this.handleFocus,
                type: (this.props.toggleable && this.state.visible) ? 'text' : this.props.type,
                className: utils.classNames(classes)
            };
            if (this.props.type == 'file') {
                props.onChange = this.readFile;
            } else {
                props.onChange = this.props.debounce ? this.debouncedChange : this.onChange;
            }
            var Tag = _.contains(['select', 'textarea'], this.props.type) ? this.props.type : 'input',
                input = <Tag {...this.props} {...props}>{this.props.children}</Tag>,
                isCheckboxOrRadio = this.isCheckboxOrRadio(),
                inputWrapperClasses = {
                    'input-group': this.props.toggleable,
                    'custom-tumbler': isCheckboxOrRadio,
                    textarea: this.props.type == 'textarea'
                };
            if (this.props.type == 'file') {
                input = <form ref='form'>{input}</form>;
            }
            return (
                <div key='input-group' className={utils.classNames(inputWrapperClasses)}>
                    {input}
                    {this.props.type == 'file' &&
                        <div className='input-group'>
                            <input
                                className='form-control file-name'
                                type='text'
                                placeholder={i18n('controls.file.placeholder')}
                                value={this.state.fileName && '[' + utils.showSize(this.state.content.length) + '] ' + this.state.fileName}
                                onClick={this.pickFile}
                                disabled={this.props.disabled}
                                readOnly
                            />
                            <div className='input-group-addon' onClick={this.state.fileName ? this.removeFile : this.pickFile}>
                                <i className={this.state.fileName && !this.props.disabled ? 'glyphicon glyphicon-remove' : 'glyphicon glyphicon-file'} />
                            </div>
                        </div>
                    }
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
        renderLabel(children) {
            if (!this.props.label && !children) return null;
            return (
                <label key='label' htmlFor={this.props.id}>
                    {children}
                    {this.props.label}
                    {this.props.tooltipText &&
                        <controls.Tooltip text={this.props.tooltipText} placement={this.props.tooltipPlacement}>
                            <i className={utils.classNames('glyphicon tooltip-icon', this.props.tooltipIcon)} />
                        </controls.Tooltip>
                    }
                </label>
            );
        },
        renderDescription() {
            var text = !_.isUndefined(this.props.error) && !_.isNull(this.props.error) ? this.props.error : this.props.description || '';
            return <span key='description' className='help-block'>{text}</span>;
        },
        renderWrapper(children) {
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
        render() {
            if (this.props.type == 'hidden' && !this.props.description && !this.props.label) return null;
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
        propTypes: {
            name: React.PropTypes.string,
            values: React.PropTypes.arrayOf(React.PropTypes.object).isRequired,
            label: React.PropTypes.node,
            tooltipText: React.PropTypes.node
        },
        render() {
            return (
                <div className='radio-group'>
                    {this.props.label &&
                        <h4>
                            {this.props.label}
                            {this.props.tooltipText &&
                                <controls.Tooltip text={this.props.tooltipText} placement='right'>
                                    <i className='glyphicon glyphicon-warning-sign tooltip-icon' />
                                </controls.Tooltip>
                            }
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

    controls.ProgressBar = React.createClass({
        propTypes: {
            wrapperClassName: React.PropTypes.node,
            progress: React.PropTypes.number
        },
        render() {
            var wrapperClasses = {
                progress: true
            };
            wrapperClasses[this.props.wrapperClassName] = this.props.wrapperClassName;

            var isInfinite = !_.isNumber(this.props.progress);
            var progressClasses = {
                'progress-bar': true,
                'progress-bar-striped active': isInfinite
            };

            return (
                <div className={utils.classNames(wrapperClasses)}>
                    <div
                        className={utils.classNames(progressClasses)}
                        role='progressbar'
                        style={{width: isInfinite ? '100%' : _.max([this.props.progress, 3]) + '%'}}
                    >
                        {!isInfinite && this.props.progress + '%'}
                    </div>
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
        render() {
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
        getDefaultProps() {
            return {placement: 'bottom'};
        },
        render() {
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

    controls.Tooltip = React.createClass({
        propTypes: {
            container: React.PropTypes.node,
            placement: React.PropTypes.node,
            text: React.PropTypes.node
        },
        getDefaultProps() {
            return {
                placement: 'top',
                container: 'body',
                wrapperClassName: 'tooltip-wrapper'
            };
        },
        componentDidMount() {
            if (this.props.text) this.addTooltip();
        },
        componentDidUpdate() {
            if (this.props.text) {
                this.updateTooltipTitle();
            } else {
                this.removeTooltip();
            }
        },
        componentWillUnmount() {
            this.removeTooltip();
        },
        addTooltip() {
            $(ReactDOM.findDOMNode(this.refs.tooltip)).tooltip({
                container: this.props.container,
                placement: this.props.placement,
                title: this.props.text
            });
        },
        updateTooltipTitle() {
            $(ReactDOM.findDOMNode(this.refs.tooltip)).attr('title', this.props.text).tooltip('fixTitle');
        },
        removeTooltip() {
            $(ReactDOM.findDOMNode(this.refs.tooltip)).tooltip('destroy');
        },
        render() {
            if (!this.props.wrap) return React.cloneElement(React.Children.only(this.props.children), {ref: 'tooltip'});
            return (
                <div className={this.props.wrapperClassName} ref='tooltip'>
                    {this.props.children}
                </div>
            );
        }
    });

    return controls;
});
