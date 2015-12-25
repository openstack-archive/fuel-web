/*eslint-disable strict*/
module.exports = {
    entry: [
        'babel-core/polyfill',
        './static/app.js'
    ],
    output: {
        path: __dirname + '/static/build/',
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
            {test: /\.css$/, loader: 'style!css!postcss'},
            {test: /\.less$/, loader: 'style!css!postcss!less'},
            {test: /\.html$/, loader: 'raw'},
            {test: /\.json$/, loader: 'json'},
            {test: /\.jison$/, loader: 'jison'},
            {test: /\.(gif|png)$/, loader: 'file'},
            {test: /\.(woff|woff2|ttf|eot|svg)(\?v=\d+\.\d+\.\d+)?$/, loader: 'file'}
        ]
    },
    resolve: {
        modulesDirectories: ['static', 'node_modules', 'vendor/custom'],
        extensions: ['', '.js'],
        alias: {
            underscore: 'lodash',
            react: 'react',
            'react-dom': 'react-dom'
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
