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
            return $1.getValue() == $3.getValue();
        })}
    | e NOT_EQUALS e
        {$$ = new yy.SubexpressionWrapper(function() {
            return $1.getValue() != $3.getValue();
        })}
    | LPAREN e RPAREN
        {$$ = new yy.SubexpressionWrapper(function() {
            return $2.getValue();
        })}
    | e AND e
        {$$ = new yy.SubexpressionWrapper(function() {
            return $1.getValue() && $3.getValue();
        })}
    | e OR e
        {$$ = new yy.SubexpressionWrapper(function() {
            return $1.getValue() || $3.getValue();
        })}
    | NOT e
        {$$ = new yy.SubexpressionWrapper(function() {
            return !($2.getValue());
        })}
    | e IN e
        {$$ = new yy.SubexpressionWrapper(function() {
            return require('underscore').contains($3.getValue(), $1.getValue());
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
        {$$ = new yy.ModelPathWrapper(yytext)}
    ;
