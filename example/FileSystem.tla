------------------- MODULE FileSystem -----------------------
\* A small example spec of some file system operations.
\* This spec is meant for use in the `app.py` in the same directory,
\* which demonstrates use of the chai client for interacting with
\* the Apalache server.

EXTENDS Apalache, Variants, Sequences, Integers, FiniteSets


\*********\
\* STATE *\
\*********\

CONSTANT
    \* The names that can be used as path segments.
    \* @type: Set(Str);
    Names

VARIABLES
    \* The set of all files in the system.
    \* @type: Set($file);
    files,
    \* The command issued.
    \* @type: $cmd;
    cmd


\**********\
\* DOMAIN *\
\**********\

\** Representation of files, identified by their kind and their path.
\*
\* @typeAlias: path = Seq(Str);
\* @typeAlias: file = File($path) | Dir($path);
\* @type: $path => $file;
File(path) == Variant("File", path)
\* @type: $path => $file;
Dir(path) == Variant("Dir", path)

IsDir(f) == "Dir" = VariantTag(f)
IsFile(f) == "File" = VariantTag(f)

\* @type: $file => $path;
FilePath(f) == VariantGetOrElse("Dir", f, VariantGetUnsafe("File", f))

\* @type: (Seq(a), Seq(a)) => Bool;
IsPrefix(prefix, s) ==
  /\ Len(s) >= Len(prefix)
  /\ \A i \in DOMAIN prefix: prefix[i] = s[i]

\** The children of a file (i.e., the contents of a directory)
\*
\* NOTE: The `Children` relation is reflexive: each file is its own child.
\*
\* @type: $file => Set($file);
Children(p) ==
  { child \in files: IsPrefix(FilePath(p), FilePath(child)) }

\* @type: Seq($file);
NoFile == <<>>

\** Representation of commands that operate on the file system.
\*
\* A $cmd is a triple holding:
\*
\* - the command name
\* - the path(s) it operates on
\* - the command's output (if any)
\*
\* @typeAlias: cmd = << Str, Seq($file), Set($file) >> ;
\* @type: $file => $cmd;
TouchCmd(p) == << "Touch", <<p>>, {} >>
\* @type: $file => $cmd;
MkDirCmd(p) == << "MkDir", <<p>>, {} >>
\* @type: $file => $cmd;
LsCmd(p)    == << "Ls", <<p>>, Children(p) >>
\* @type: () => $cmd;
None == << "None", NoFile, {} >>


\***********\
\* ACTIONS *\
\***********\

\* @type: ($file, Str) => Bool;
Touch(dir, name) ==
  LET newFile == File(Append(FilePath(dir), name)) IN
  /\ files' = { newFile } \union files
  /\ cmd' = TouchCmd(newFile)


\* @type: ($file, Str) => Bool;
MkDir(dir, name) ==
  LET newDir == Dir(Append(FilePath(dir), name)) IN
  /\ files' = { newDir } \union files
  /\ cmd' = MkDirCmd(newDir)

\* @type: $file => Bool;
Ls(p) ==
  /\ cmd' = LsCmd(p)
  /\ UNCHANGED files

Next ==
  \E f \in files:
    \/ /\ IsDir(f)
      /\ \E n \in Names:
        \/ Touch(f, n)
        \/ MkDir(f, n)
    \/ Ls(f)


\******************\
\* INITIALIZATION *\
\******************\

CInit == Names = {"foo", "bar", "baz"}

Init ==
  /\ files = { Dir(<<"/">>) }
  /\ cmd = None


\**************\
\* INVARIANTS *\
\**************\

MinPathLength == 5
MinDirSize == 5

Inv ==
  ~ /\ \E p \in files: Len(FilePath(p)) > MinPathLength
    /\ Cardinality(cmd[3]) > MinDirSize

\* @type: << Set($file), $cmd >>;
View == << files, cmd >>
============================================================
