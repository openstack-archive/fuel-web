/*eslint-disable strict*/

module.exports = {
  entry: [
    'babel-core/polyfill',
    './static/app.js'
  ],
  output: {
    path: require('path').join(__dirname, '/static/build/'),
    publicPath: '/static/build/',
    filename: 'bundle.js',
    chunkFilename: null,
    sourceMapFilename: 'bundle.js.map'
  },
  module: {
    loaders: [
      {
        test: /\.js$/,
        loader: 'babel',
        exclude: [/(node_modules|vendor\/custom)\//, /\/expression\/parser\.js$/],
        query: {cacheDirectory: true}
      },
      {test: /\/expression\/parser\.js$/, loader: 'exports?parser'},
      {test: require.resolve('jquery'), loader: 'expose?jQuery!expose?$'},
      {
        test: /\/sinon\.js$/,
        loader: 'imports?this=>window,define=>false,exports=>false,module=>false,require=>false'
      },
      {test: /\.css$/, loader: 'style!css!postcss'},
      {test: /\.less$/, loader: 'style!css!postcss!less'},
      {test: /\.html$/, loader: 'raw'},
      {test: /\.json$/, loader: 'json'},
      {test: /\.jison$/, loader: 'jison'},
      {test: /\.(gif|png|jpg)$/, loader: 'file'},
      {test: /\.(woff|woff2|ttf|eot|svg)(\?v=\d+\.\d+\.\d+)?$/, loader: 'file'}
    ]
  },
  resolve: {
    modulesDirectories: ['static', 'node_modules', 'vendor/custom'],
    extensions: ['', '.js'],
    alias: {
      underscore: 'lodash',
      sinon: 'sinon/pkg/sinon.js'
    }
  },
  node: {},
  plugins: [],
  postcss: function() {
    return [require('autoprefixer')];
  },
  devtool: 'cheap-module-source-map',
  watchOptions: {
    aggregateTimeout: 300,
    poll: 1000
  }
};
