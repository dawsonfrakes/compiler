from dataclasses import dataclass
from enum import IntEnum

class TokenKind(IntEnum):
    INVALID = 0
    EOF = 128
    ERROR = 129
    IDENTIFIER = 130
    NUMBER = 131
    STRING = 132
    TYPE = 133

    KEYWORD_STRUCT = 148
    KEYWORD_FOREIGN = 149
    KEYWORD_PROC = 150
    KEYWORD_CALLCONV = 151

    def as_str(t: int) -> str: return TokenKind(t).name if t in TokenKind else f"'{chr(t)}'"

keywords = {
    "struct": TokenKind.KEYWORD_STRUCT,
    "foreign": TokenKind.KEYWORD_FOREIGN,
    "proc": TokenKind.KEYWORD_PROC,
    "callconv": TokenKind.KEYWORD_CALLCONV,
}

@dataclass
class Token:
    offset: int
    length: int
    kind: int

class Type_Kind(IntEnum):
    INVALID = 0
    NORETURN = 1
    INTEGER = 2

@dataclass
class Type_Info:
    kind: Type_Kind

@dataclass
class Type_Info_Noreturn(Type_Info):
    kind = Type_Kind.NORETURN

@dataclass
class Type_Info_Integer(Type_Info):
    kind = Type_Kind.INTEGER
    bits: int
    signed: bool

type_noreturn = Type_Info_Noreturn(Type_Kind.NORETURN)
type_c_uint = Type_Info_Integer(Type_Kind.INTEGER, 32, False)

class Code_Node_Kind(IntEnum):
    INVALID = 0
    DECLARATION = 1
    FOREIGN = 2
    STRUCT = 3
    PROCEDURE_HEADER = 4
    PROCEDURE_BODY = 5
    TYPE = 6
    IDENT = 7
    CALL = 8
    NUMBER = 9
    FIELD = 10

@dataclass
class Code_Node:
    kind: Code_Node_Kind

@dataclass
class Code_Declaration(Code_Node):
    kind = Code_Node_Kind.DECLARATION
    identifier: Token
    type_expr: Code_Node | None
    value_expr: Code_Node | None
    constant: bool

@dataclass
class Code_Foreign(Code_Node):
    kind = Code_Node_Kind.FOREIGN
    library: str | None
    value_expr: Code_Node

@dataclass
class Code_Struct(Code_Node):
    kind = Code_Node_Kind.STRUCT
    members: list[Code_Node]

@dataclass
class Code_Procedure_Header(Code_Node):
    kind = Code_Node_Kind.PROCEDURE_HEADER
    arg_names: list[Token]
    arg_types: list[Code_Node]
    return_type: Code_Node
    callconv: Code_Node | None

@dataclass
class Code_Procedure_Body(Code_Node):
    kind = Code_Node_Kind.PROCEDURE_BODY
    header: Code_Procedure_Header
    statements: list[Code_Node]

@dataclass
class Code_Type(Code_Node):
    kind = Code_Node_Kind.TYPE
    info: Type_Info

@dataclass
class Code_Ident(Code_Node):
    kind = Code_Node_Kind.IDENT
    ident: Token

@dataclass
class Code_Call(Code_Node):
    kind = Code_Node_Kind.CALL
    lhs: Code_Node
    args: list[Code_Node]

@dataclass
class Code_Number(Code_Node):
    kind = Code_Node_Kind.NUMBER
    value: Token

@dataclass
class Code_Field(Code_Node):
    kind = Code_Node_Kind.FIELD
    path: Code_Node
    field: Token

class Parser:
    def __init__(self, s: str) -> None:
        self.s, self.p = s, 0

    def token_at(self, p: int) -> Token:
        while p < len(self.s) and self.s[p].isspace(): p += 1
        kind = TokenKind.INVALID
        l = 1
        if p >= len(self.s): kind = TokenKind.EOF
        elif self.s[p].isalpha() or self.s[p] == '_':
            kind = TokenKind.IDENTIFIER
            while p + l < len(self.s) and (self.s[p + l].isalnum() or self.s[p + l] == '_'): l += 1
            if self.s[p:p + l] in ["c_uint", "noreturn"]:
                kind = TokenKind.TYPE
            elif self.s[p:p + l] in keywords:
                kind = keywords[self.s[p:p + l]]
        elif self.s[p] == '"':
            kind = TokenKind.STRING
            while p + l < len(self.s) and (self.s[p + l - 1] == '\\' or self.s[p + l] != '"'): l += 1
            if p + l >= len(self.s) or self.s[p + l] != '"':
                kind = TokenKind.ERROR
            else: l += 1
        elif self.s[p].isdigit():
            kind = TokenKind.NUMBER
            while p + l < len(self.s) and self.s[p + l].isdigit(): l += 1
        elif self.s[p] in ".:=+-*/<>(){}[]": kind = ord(self.s[p])
        else:
            kind = TokenKind.ERROR
        return Token(p, l, int(kind))

    def print_all_tokens(self) -> None:
        while True:
            token = self.token_at(self.p)
            if token.kind == TokenKind.EOF: break
            if token.kind == TokenKind.ERROR:
                raise ValueError(self.s[token.offset:][:token.length])
            self.p = token.offset + token.length
            print(TokenKind.as_str(token.kind), self.s[token.offset:][:token.length])

    def eat(self, expect: int) -> Token:
        token = self.token_at(self.p)
        if token.kind != expect: raise ValueError(f"expected {TokenKind.as_str(expect)}, got {token}")
        self.p = token.offset + token.length
        return token

    def peek(self, n: int = 1) -> Token:
        token = None
        p = self.p
        for _ in range(n):
            token = self.token_at(p)
            p = token.offset + token.length
        return token

    def parse_expression(self) -> Code_Node:
        result = None
        token = self.peek()
        if token.kind == TokenKind.KEYWORD_FOREIGN:
            self.eat(TokenKind.KEYWORD_FOREIGN)
            library = None
            if self.peek().kind == TokenKind.STRING:
                library = self.eat(TokenKind.STRING)
            type_expr = self.parse_expression()
            result = Code_Foreign(Code_Node_Kind.FOREIGN, library, type_expr)
        elif token.kind == TokenKind.KEYWORD_PROC:
            self.eat(TokenKind.KEYWORD_PROC)
            self.eat(ord('('))
            arg_names = []
            arg_types = []
            while self.peek().kind != ord(')'):
                if self.peek(2).kind == ord(':'):
                    arg_names.append(self.eat(TokenKind.IDENTIFIER))
                    self.eat(ord(':'))
                arg_types.append(self.parse_expression())
                if self.peek().kind == ord(','): self.eat(ord(','))
                else: break
            self.eat(ord(')'))
            assert len(arg_names) == len(arg_types) or len(arg_names) == 0
            callconv = None
            if self.peek().kind == TokenKind.KEYWORD_CALLCONV:
                self.eat(TokenKind.KEYWORD_CALLCONV)
                self.eat(ord('('))
                callconv = self.parse_expression()
                self.eat(ord(')'))
            return_type = self.parse_expression()
            header = Code_Procedure_Header(Code_Node_Kind.PROCEDURE_HEADER, arg_names, arg_types, return_type, callconv)
            if self.peek().kind == ord('{'):
                self.eat(ord('{'))
                statements = []
                while self.peek().kind != ord('}'):
                    statements.append(self.parse_expression())
                self.eat(ord('}'))
                result = Code_Procedure_Body(Code_Node_Kind.PROCEDURE_BODY, header, statements)
            else: result = header
        elif token.kind == TokenKind.KEYWORD_STRUCT:
            self.eat(TokenKind.KEYWORD_STRUCT)
            self.eat(ord('{'))
            members = []
            while self.peek().kind != ord('}'):
                members.append(self.parse_declaration())
            self.eat(ord('}'))
            result = Code_Struct(Code_Node_Kind.STRUCT, members)
        elif token.kind == TokenKind.TYPE:
            x = self.s[token.offset:][:token.length]
            if x == "noreturn":
                self.eat(TokenKind.TYPE)
                result = Code_Type(Code_Node_Kind.TYPE, type_noreturn)
            elif x == "c_uint":
                self.eat(TokenKind.TYPE)
                result = Code_Type(Code_Node_Kind.TYPE, type_c_uint)
            else:
                print(self.s[token.offset:][:token.length])
        elif token.kind == TokenKind.IDENTIFIER:
            ident = self.eat(TokenKind.IDENTIFIER)
            result = Code_Ident(Code_Node_Kind.IDENT, ident)
        elif token.kind == TokenKind.NUMBER:
            number = self.eat(TokenKind.NUMBER)
            result = Code_Number(Code_Node_Kind.NUMBER, number)

        if result is None: raise NotImplementedError(TokenKind.as_str(token.kind))

        if self.peek().kind == ord('.'):
            self.eat(ord('.'))
            field = self.eat(TokenKind.IDENTIFIER)
            result = Code_Field(Code_Node_Kind.FIELD, result, field)

        if self.peek().kind == ord('('):
            self.eat(ord('('))
            args = []
            while self.peek().kind != ord(')'):
                args.append(self.parse_expression())
            self.eat(ord(')'))
            result = Code_Call(Code_Node_Kind.CALL, result, args)

        if result is not None: return result
        raise NotImplementedError(TokenKind.as_str(token.kind))

    def parse_declaration(self) -> Code_Declaration:
        identifier = self.eat(TokenKind.IDENTIFIER)
        self.eat(ord(':'))
        type_expr = None
        if self.peek().kind not in [ord(':'), ord('=')]:
            type_expr = self.parse_expression()
        constant = False
        value_expr = None
        if self.peek().kind in [ord(':'), ord('=')]:
            constant = self.eat(self.peek().kind).kind == ord(':')
            value_expr = self.parse_expression()
        assert type_expr is not None or value_expr is not None
        return Code_Declaration(Code_Node_Kind.DECLARATION, identifier, type_expr, value_expr, constant)

    def parse_module(self) -> list[Code_Node]:
        result = []
        while parser.peek().kind != TokenKind.EOF:
            decl = parser.parse_declaration()
            print(decl)
            result.append(decl)
        return result

class CVisitor:
    def __init__(self, parser: Parser) -> None:
        self.parser = parser

    def visit(self, node: Code_Node):
        if node.kind == Code_Node_Kind.IDENT:
            return self.parser.s[node.token.offset:][:node.token.length]
        if node.kind == Code_Node_Kind.DECLARATION:
            result = ""
            name = self.parser.s[node.identifier.offset:][:node.identifier.length]
            value_expr = node.value_expr
            if value_expr.kind == Code_Node_Kind.STRUCT:
                result += f"struct {name} {{\n"
                result += "};\n\n"
                return result
            if value_expr.kind == Code_Node_Kind.PROCEDURE_BODY:
                result += f"void {name}() {{"
                result += "}\n\n"
                return result
            raise NotImplementedError(value_expr.kind.name)
        raise NotImplementedError(node.kind.name)

    def visit_module(self, module: list[Code_Node]) -> str:
        result = ""
        for node in module:
            result += self.visit(node)
        return result

src = """
kernel32 :: struct {
    ExitProcess :: foreign "kernel32" proc (c_uint) callconv(WINAPI) noreturn
}

RawEntryPoint :: proc () callconv(WINAPI) noreturn {
    kernel32.ExitProcess(0)
}
"""

parser = Parser(src)
module = parser.parse_module()
for node in module: print(f"{node}\n")
visitor = CVisitor(parser)
print(visitor.visit_module(module))
