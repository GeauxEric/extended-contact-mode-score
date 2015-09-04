#!/usr/bin/env python

import luigi
import pickle
import json
import os
import pandas as pd
from urls import WORKING_DIR
from xcms import LpcApocXcms
from apoc_inputs import ApocListPathTask
from run_control_apoc import LpcApocResultTask, ApocResultParer


class ApocPocketsResultsCollection(luigi.Task):

    subset = luigi.Parameter(default="rs2")

    def requires(self):
        return ApocListPathTask(self.subset)

    def output(self):
        path = os.path.join(WORKING_DIR, self.subset + "_ps_score.pkl")
        return luigi.LocalTarget(path)

    def run(self):
        results = {}
        with self.requires().output().open('r') as f:
            for line in f.read().splitlines():
                tname, qname = line.split()
                key = tname + " " + qname
                apoc_result = LpcApocResultTask(tname, qname, self.subset)
                try:
                    with apoc_result.output().open('r') as apoc_f:
                        parser = ApocResultParer(apoc_f.read())
                        pocket_alignment = parser.queryPocket(tname, qname)
                        global_alignment = parser.queryGlobal(tname, qname)
                        tm_score = global_alignment.tm_score
                        ps_score = pocket_alignment.ps_score
                        results[key] = {"ps_score": ps_score,
                                        "tm_score": tm_score}
                except:
                    results[key] = None

        to_write = json.dumps(results, sort_keys=True,
                              indent=4, separators=(',', ': '))
        with self.output().open('w') as f:
            pickle.dump(to_write, f)


class ApocPocketsResultsTable(luigi.Task):

    subset = luigi.Parameter()

    def requires(self):
        return ApocPocketsResultsCollection(self.subset)

    def output(self):
        path = os.path.join(WORKING_DIR, self.subset + "_apoc_scores.csv")
        return luigi.LocalTarget(path)

    def _run(self):
        with self.requires().output().open('r') as inputObj:
            data = json.loads(pickle.load(inputObj))
            dset = pd.DataFrame(data)
            dset = dset.T
            dset.to_csv(self.output().path)

    def run(self):
        self._run()


class AtomicXcmsCollection(luigi.Task):

    subset = luigi.Parameter(default="subject")

    def requires(self):
        return ApocListPathTask(self.subset)

    def output(self):
        collected = os.path.join(WORKING_DIR, self.subset + "_atmic_xcms.pkl")
        missed = os.path.join(WORKING_DIR, self.subset + "_atmic_xcms.missed")
        return luigi.LocalTarget(collected), luigi.LocalTarget(missed)

    def run(self):
        collected, missed = self.output()
        collected_content = {}
        missed_content = []
        with self.requires().output().open('r') as f:
            lines = f.read().splitlines()
            for line in lines:
                try:
                    tname, qname = line.split()
                    key = tname + " " + qname
                    lpc_result = LpcApocXcms(tname, qname, self.subset).output()
                    if lpc_result.exists():
                        with lpc_result.open('r') as f:
                            collected_content[key] = json.loads(f.read())
                    else:
                        missed_content.append(key)
                except ValueError:
                    print "ERROR!", line
                    pass

        with collected.open('w') as f:
            pickle.dump(collected_content, f)

        with missed.open('w') as f:
            for key in missed_content:
                f.write(key + "\n")


class AtomicXcmsTable(luigi.Task):

    subset = luigi.Parameter()

    def requires(self):
        return AtomicXcmsCollection(self.subset)

    def output(self):
        csv_path = os.path.join(WORKING_DIR, self.subset + "_atmic_xcms.csv")
        return luigi.LocalTarget(csv_path)

    def run(self):
        collected, missed = self.requires().output()
        with collected.open('r') as f:
            dicts = pickle.load(f)

        cols = ['Apoc ps-score', 'Kcombu tanimoto',
                'xcms', '# ligand atoms', '# residue atoms']
        datas = []
        # TODO: calculate the fraction of contact
        for key, data in dicts.iteritems():
            tname, qname = key.split()
            try:
                mydata = [data[_] for _ in cols]
                mydata.append(tname)
                mydata.append(qname)
                datas.append(mydata)
            except:
                print tname, qname

        cols = cols + ['tname', 'qname']
        dset = pd.DataFrame(datas, columns=cols)
        dset.to_csv(self.output().path)


def main():
    luigi.build([AtomicXcmsCollection("subject"),
                 AtomicXcmsCollection("rs2"),
                 AtomicXcmsTable("subject"),
                 ApocListPathTask("rs2"),
                 ApocPocketsResultsCollection("rs2"),
                 ApocPocketsResultsTable("rs2"),
                 AtomicXcmsTable("rs2")],
                local_scheduler=True)


if __name__ == '__main__':
    main()
