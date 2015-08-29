/*eslint-disable strict*/
module.exports = {
    entry: ['./static/app.js'],
    output: {
        path: __dirname + '/static/build/',
        publicPath: '/static/build/',
        filename: 'bundle.js',
        chunkFilename: null,
        sourceMapFilename: 'bundle.js.map'
    },
    module: {
        loaders: [
            {test: /\/expression\/parser\.js$/, loader: 'exports?parser'},
            {test: require.resolve('jquery'), loader: 'expose?jQuery!expose?$'},
            {test: /\.css$/, loader: 'style!css!postcss'},
            {test: /\.less$/, loader: 'style!css!postcss!less'},
            {test: /\.html$/, loader: 'raw'},
            {test: /\.json$/, loader: 'json'},
            {test: /\.jison$/, loader: 'jison'},
            {test: /\.jsx$/, loader: 'babel', exclude: /(node_modules|bower_components)/},
            {test: /\.(woff|woff2|ttf|eot|svg)(\?v=\d+\.\d+\.\d+)?$/, loader: 'file'},
            {test: /\.(gif|png)$/, loader: 'file'}
        ]
    },
    resolve: {
        modulesDirectories: ['static', 'node_modules', 'vendor/custom'],
        extensions: ['', '.js', '.jsx'],
        alias: {
            underscore: 'lodash',
            react: 'react/addons',
            // FIXME(vkramskikh): node.js version depends on express
            // and causes warnings
            i18next: 'i18next/lib/dep/i18next-1.7.1.js'
        }
    },
    node: {},
    plugins: [],
    postcss: function() {
        return [require('autoprefixer')];
    },
    devtool: 'cheap-source-map',
    watchOptions: {
        aggregateTimeout: 300,
        poll: 1000
    }
};
