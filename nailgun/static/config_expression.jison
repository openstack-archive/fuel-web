%lex

%%
\s+                          /* skip whitespace */
\-?[0-9]+("."[0-9]+)?\b      return 'NUMBER';
\"(.*?)\"                    return 'STRING';
\'(.*?)\'                    return 'STRING';
true                         return 'TRUE';
false                        return 'FALSE';
null                         return 'NULL';
"in"                         return 'IN';
"and"                        return 'AND';
"or"                         return 'OR';
"not"                        return 'NOT';
(\w*?\:)?[\w\.\-]+\??        return 'MODELPATH';
"=="                         return 'EQUALS';
"!="                         return 'NOT_EQUALS';
"("                          return 'LPAREN';
")"                          return 'RPAREN';
<<EOF>>                      return 'EOF';

/lex

/* operator associations and precedence */

%left 'OR'
%left 'AND'
%left 'EQUALS' 'NOT_EQUALS'
%left 'IN' 'NOT'

%start expressions

%% /* language grammar */

expressions
    : e EOF
        {return $1;}
    ;

e
    : e EQUALS e
        {$$ = $1 == $3;}
    | e NOT_EQUALS e
        {$$ = $1 != $3;}
    | LPAREN e RPAREN
        {$$ = $2;}
    | e AND e
        {$$ = $1 && $3;}
    | e OR e
        {$$ = $1 || $3;}
    | NOT e
        {$$ = !$2;}
    | e IN e
        {$$ = yy._.contains($3, $1);}
    | NUMBER
        {$$ = Number(yytext);}
    | STRING
        {$$ = yytext.slice(1, -1);}
    | TRUE
        {$$ = true;}
    | FALSE
        {$$ = false;}
    | NULL
        {$$ = null;}
    | MODELPATH
        {
            var strict = yy.options.strict;
            if (yytext.slice(-1) == '?') {
                strict = false;
                yytext = yytext.slice(0, -1);
            }
            var modelPath = yy.utils.parseModelPath(yytext, yy.models);
            $$ = modelPath.get();
            if (typeof $$ == 'undefined') {
                if (strict) {
                    throw new TypeError('Value of ' + yytext + ' is undefined. Set options.strict to false to allow undefined values.');
                }
                $$ = null;
            }
            yy.modelPaths[yytext] = modelPath;
        }
    ;