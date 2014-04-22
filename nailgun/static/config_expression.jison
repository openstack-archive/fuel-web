%lex

%%
\s+                          /* skip whitespace */
\-?[0-9]+("."[0-9]+)?\b      return 'NUMBER';
\"(.*?)\"                    return 'STRING';
\'(.*?)\'                    return 'STRING';
(True|true)                  return 'TRUE';
(False|false)                return 'FALSE';
"and"                        return 'AND';
"or"                         return 'OR';
"not"                        return 'NOT';
(\w*?\:)?[\w\.\-]+           return 'MODELPATH';
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
%left 'NOT'

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
    | 'NOT' e
        {$$ = !$2;}
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