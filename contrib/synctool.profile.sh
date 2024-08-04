#!/bin/bash
if [ "$EUID" = "0" ]; then
    case :$PATH: in
        *:/opt/synctool/bin:*) ;;
        *) PATH=$PATH:/opt/synctool/bin ;;
    esac
    export PATH
fi
