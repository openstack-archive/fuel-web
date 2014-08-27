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
        {$$ = new yy.SubexpressionWrapper(function() {
            return $1.evaluate() == $3.evaluate();
        })}
    | e NOT_EQUALS e
        {$$ = new yy.SubexpressionWrapper(function() {
            return $1.evaluate() != $3.evaluate();
        })}
    | LPAREN e RPAREN
        {$$ = new yy.SubexpressionWrapper(function() {
            return $2.evaluate();
        })}
    | e AND e
        {$$ = new yy.SubexpressionWrapper(function() {
            return $1.evaluate() && $3.evaluate();
        })}
    | e OR e
        {$$ = new yy.SubexpressionWrapper(function() {
            return $1.evaluate() || $3.evaluate();
        })}
    | NOT e
        {$$ = new yy.SubexpressionWrapper(function() {
            return !($2.evaluate());
        })}
    | e IN e
        {$$ = new yy.SubexpressionWrapper(function() {
            return yy._.contains($3, $1);
        })}
    | NUMBER
        {$$ = new yy.ScalarWrapper(Number(yytext))}
    | STRING
        {$$ = new yy.ScalarWrapper(yytext.slice(1, -1))}
    | TRUE
        {$$ = new yy.ScalarWrapper(true)}
    | FALSE
        {$$ = new yy.ScalarWrapper(false)}
    | NULL
        {$$ = new yy.ScalarWrapper(null)}
    | MODELPATH
        {
            var strict = yy.expression.options.strict;
            if (yytext.slice(-1) == '?') {
                strict = false;
                yytext = yytext.slice(0, -1);
            }
            $$ = new yy.ModelPathWrapper(yytext, yy.expression, strict);
        }
    ;