#!/bin/bash

helm template koldavar \
    ./k8s/helm/koldavar-chart \
    -f ./k8s/helm/koldavar-chart/values.yaml \
    | kubectl apply -f -