#!/usr/bin/env python

import luigi
import pybel
import json
import pandas as pd
from cms_vals_for_p_val import PairwiseCms
from sample_confs import SampleConf
from vina import Path


class CollectGridCms(luigi.Task):

    def getSdfs(self):
        return [_.rstrip() for _ in file("../dat/astex_sdf.lst")]

    def requires(self):
        sdfs = self.getSdfs()
        return [PairwiseCms(sdf) for sdf in sdfs]

    def output(self):
        path = "../dat/astex_grid_cms.json"
        return luigi.LocalTarget(path)

    def run(self):
        dset = {}
        for job in self.requires():
            with job.output().open('r') as ifs:
                sdf_id = job.sdf_id
                lines = ifs.readlines()
                cms_lines = filter(lambda line: "cms value" in line, lines)
                cms_valus = map(lambda line: float(line.split()[-1]),
                                cms_lines)
                if len(cms_valus) > 0:
                    dset[sdf_id] = cms_valus

        to_write = json.dumps(dset, indent=4, separators=(',', ': '))
        with open(self.output().path, 'w') as ofs:
            ofs.write(to_write)


class ComplexSizes(CollectGridCms):

    def output(self):
        path = "../dat/astex_sz.csv"
        return luigi.LocalTarget(path)

    def requires(self):
        pass

    def run(self):
        data = {}
        for sdf_id in self.getSdfs():
            path = Path(sdf_id)
            lig = pybel.readfile('sdf', path.astex_sdf()).next()
            lig.removeh()
            prt = pybel.readfile('pdb', path.astex_pdb()).next()
            prt.removeh()
            lig_sz = len(lig.atoms)
            prt_sz = len(prt.atoms)
            data[sdf_id] = {"lig_sz": lig_sz,
                            "prt_sz": prt_sz}
        dset = pd.DataFrame(data)
        dset.to_csv(self.output().path)


class CollectGridDsets(CollectGridCms):

    def requires(self):
        sdfs = self.getSdfs()
        return [SampleConf(sdf) for sdf in sdfs]

    def output(self):
        path = "../dat/astex_grid_dsets.csv"
        return luigi.LocalTarget(path)

    def run(self):
        all_dsets = pd.DataFrame()
        for job in self.requires():
            ifn = job.output().path
            lines = [_ for _ in file(ifn)]
            if len(lines) > 0:
                dset = pd.read_csv(ifn, sep=' ', index_col=None)
                if len(dset) < 100:
                    print job.sdf_id, len(dset)
                all_dsets = pd.concat([all_dsets, dset])

        all_dsets.to_csv(self.output().path)


def main():
    luigi.build([CollectGridCms(),
                 CollectGridDsets(),
                 ComplexSizes()],
                local_scheduler=True)
    pass


if __name__ == '__main__':
    main()