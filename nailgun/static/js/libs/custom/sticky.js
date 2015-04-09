/*
 *  Taken from https://github.com/captivationsoftware/react-sticky
 *
 *  The MIT License (MIT)
 *
 *  Copyright (c) 2014 captivationsoftware
 *
 *  Permission is hereby granted, free of charge, to any person obtaining a copy
 *  of this software and associated documentation files (the "Software"), to deal
 *  in the Software without restriction, including without limitation the rights
 *  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 *  copies of the Software, and to permit persons to whom the Software is
 *  furnished to do so, subject to the following conditions:
 *  
 *  The above copyright notice and this permission notice shall be included in all
 *  copies or substantial portions of the Software.
 *  
 *  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 *  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 *  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 *  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 *  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 *  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 *  SOFTWARE.
**/

(function() {

  var React = require('react'),
		Sticky = React.createClass({

  reset: function() {
    var html = document.documentElement,
        body = document.body,
        windowOffset = window.pageYOffset || (html.clientHeight ? html : body).scrollTop;
    
    this.elementOffset = this.getDOMNode().getBoundingClientRect().top + windowOffset;
  },

  handleResize: function() {
    // set style with callback to reset once style rendered succesfully
    this.setState({ style: {} }, this.reset);
  },

  handleScroll: function() {
    if (window.pageYOffset > this.elementOffset) this.setState({ style: this.props.stickyStyle });
    else this.setState({ style: {} });
  },

  getDefaultProps: function() {
    return {
      stickyStyle: {
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0
      }
    };
  },

  getInitialState: function() {
    return {
      style: {}
    }; 
  },

  componentDidMount: function() {
    this.reset();
    window.addEventListener('scroll', this.handleScroll);
    window.addEventListener('resize', this.handleResize);
  },

  componentWillUnmount: function() {
    window.removeEventListener('scroll', this.handleScroll);
    window.removeEventListener('resize', this.handleResize);
  },

  render: function() {
    return React.DOM.div({
      style: this.state.style
    }, this.props.children);
  }
});

//module.exports = Sticky;
return Sticky;

}(this, function(Sticky) {
  return Sticky;
}));
