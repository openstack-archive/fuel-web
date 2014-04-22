%lex

%%
\s+                          /* skip whitespace */
\-?[0-9]+("."[0-9]+)?\b      return 'NUMBER';
\"(.*?)\"                    return 'STRING';
\'(.*?)\'                    return 'STRING';
(True|true)                  return 'TRUE';
(False|false)                return 'FALSE';
(\w*?\:)?[\w\.\-]+           return 'MODELPATH';
"and"                        return 'AND';
"or"                         return 'OR';
"=="                         return '==';
"!="                         return '!=';
"("                          return '(';
")"                          return ')';
<<EOF>>                      return 'EOF';

/lex

/* operator associations and precedence */

%left 'OR'
%left 'AND'
%left '==' '!='

%start expressions

%% /* language grammar */

expressions
    : e EOF
        {return $1;}
    ;

e
    : e '==' e
        {$$ = $1 == $3;}
    | e '!=' e
        {$$ = $1 != $3;}
    | '(' e ')'
        {$$ = $2;}
    | e 'AND' e
        {$$ = $1 && $3;}
    | e 'OR' e
        {$$ = $1 || $3;}
    | NUMBER
        {$$ = Number(yytext);}
    | STRING
        {$$ = yytext.slice(1, -1);}
    | TRUE
        {$$ = true;}
    | FALSE
        {$$ = false;}
    | MODELPATH
        {$$ = yy.utils.parseModelPath(yytext, yy.models).get();}
    ;