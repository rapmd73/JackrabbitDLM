#!/bin/bash

#./LockWars 100 100000 > LW1.txt 2>&1
#N=`ps a | grep -c LockFighter | grep -v grep`
#while [ $N -gt 1 ] ; do
#    N=`ps a | grep -c LockFighter | grep -v grep`
#    sleep 1
#done
#echo LW1 finished

./LockWars 100 100000 * > LW2.txt 2>&1
N=`ps a | grep -c LockFighter | grep -v grep`
while [ $N -gt 1 ] ; do
    N=`ps a | grep -c LockFighter | grep -v grep`
    sleep 1
done
echo LW2 finished
