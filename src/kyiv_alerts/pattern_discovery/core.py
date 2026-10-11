"""Deterministic populations, Unicode n-grams and sparse exploratory grouping."""
from collections import Counter, defaultdict
from datetime import datetime
import re
import unicodedata
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.preprocessing import normalize as sparse_normalize
from threadpoolctl import threadpool_limits
from kyiv_alerts.ingestion.timeutils import KYIV
from kyiv_alerts.classification.rules import CATEGORIES

SPECIFIC = tuple(c for c in CATEGORIES if c not in {'other','unknown'})
POPULATIONS = ('specific_classified','other_only','text_unclassified','unavailable_or_unresolved')
PERIODS = ('2023-08_2023-12','2024','2025','2026-01_2026-07','2026-08_2026-09','2026-10')
# Keep short words/abbreviations: these only filter stand-alone function words.
STOPWORDS = frozenset('і й та а але або що це то як вже ще ж же не на до у в із з зі за по від над під про для при там тут його її їх ми ви він вона воно вони був була були буде є'.split())
TOKEN = re.compile(r"[а-яіїєґa-z0-9]+(?:['’ʼ][а-яіїєґa-z0-9]+)*", re.I)


def normalize_text(text):
    text = unicodedata.normalize('NFKC', text or '').casefold()
    # Remove link/account/footer noise only from the analysis representation.
    text = re.sub(r'https?://\S+|www\.\S+|(?<!\w)t\.me/\S+', ' ', text)
    text = re.sub(r'(?m)^\s*✙[^\n]*$', ' ', text)
    text = re.sub(r'(?<!\w)(?:\d{4}[ \t-]+){3}\d{4}(?!\w)', ' ', text)
    text = re.sub(r'(?<!\w)\d{5,}(?!\w)', ' ', text)
    text = text.translate(str.maketrans({'’':"'",'ʼ':"'",'`':"'",'–':'-','—':'-'}))
    return ' '.join(TOKEN.findall(text))


def word_ngrams(text):
    tokens = text.split()
    return [ ' '.join(tokens[i:i+n]) for n in (1,2,3) for i in range(len(tokens)-n+1)
             if any(t not in STOPWORDS for t in tokens[i:i+n]) ]


def period_for(instant):
    local = instant.astimezone(KYIV)
    year,month=local.year,local.month
    if year==2023 and month>=8:return PERIODS[0]
    if year==2024:return PERIODS[1]
    if year==2025:return PERIODS[2]
    if year==2026 and month<=7:return PERIODS[3]
    if year==2026 and month in (8,9):return PERIODS[4]
    if year==2026 and month==10:return PERIODS[5]
    return 'outside_requested_periods'


def eligible(feature):
    return feature['historical_range_relation']=='within' and feature['coverage_status'] in {'covered','no_messages_found'}


def population(feature):
    if any(feature[c] is True for c in SPECIFIC):return POPULATIONS[0]
    if feature['other'] is True:return POPULATIONS[1]
    if feature['classification_status']=='no_identifiable_marker' and (feature['telegram_text_message_count'] or 0)>0:return POPULATIONS[2]
    if feature['classification_status'] in {'no_linked_text','no_telegram_historical_coverage','unresolved_temporal_ambiguity','partial_historical_coverage'}:return POPULATIONS[3]
    raise ValueError('Unrecognized diagnostic population: '+str(feature['alert_id']))


def reasons(markers):
    return sorted({r for m in markers for r in (m.get('exclusion_reason') or '').split(';') if r})


def incidence(records):
    aids=sorted({r['alert_id'] for r in records})
    index={a:i for i,a in enumerate(aids)}
    return aids,sparse.csr_matrix((np.ones(len(records),dtype=np.int32),
           ([index[r['alert_id']] for r in records],np.arange(len(records)))),shape=(len(aids),len(records)))


def frequency_analysis(records, kind='word', limit=500):
    """Unique-alert/message n-gram support. CSR matrices never become N-by-N."""
    texts=[r['normalized_text'] for r in records]
    if not any(texts):return [],{},None
    vec=CountVectorizer(analyzer=word_ngrams if kind=='word' else 'char_wb',
                        ngram_range=(1,1) if kind=='word' else (3,5),min_df=3,max_features=70000,dtype=np.int32,
                        binary=True,lowercase=False)
    try:matrix=vec.fit_transform(texts)
    except ValueError as exc:
        if 'empty vocabulary' in str(exc) or 'no terms remain' in str(exc):return [],{},None
        raise
    names=vec.get_feature_names_out()
    aids,owner=incidence(records)
    alert_matrix=(owner@matrix).astype(bool).astype(np.int32)
    ap={a:records[owner.getrow(i).indices[0]]['population'] for i,a in enumerate(aids)}
    # Three populations are compared separately, never conflating B/C with A.
    flags=np.array([ap[a] in POPULATIONS[1:3] for a in aids])
    specific=np.array([ap[a]==POPULATIONS[0] for a in aids])
    msgflags=np.array([r['population'] in POPULATIONS[1:3] for r in records])
    target_support=np.asarray(alert_matrix[flags].sum(axis=0)).ravel()
    reference_support=np.asarray(alert_matrix[specific].sum(axis=0)).ravel()
    def unique_message_counts(mask):
        indices=np.flatnonzero(mask)
        ids=sorted({records[i]['message_id'] for i in indices})
        imap={m:i for i,m in enumerate(ids)}
        own=sparse.csr_matrix((np.ones(len(indices),dtype=np.int32),([imap[records[i]['message_id']] for i in indices],np.arange(len(indices)))),shape=(len(ids),len(indices)))
        return np.asarray((own@matrix[indices]).astype(bool).sum(axis=0)).ravel()
    target_messages=unique_message_counts(msgflags)
    ref_messages=unique_message_counts(~msgflags)
    targetden=int(flags.sum());refden=int(specific.sum())
    # Smoothed prevalence ratio is descriptive, not a statistical significance test.
    ratio=((target_support+.5)/(targetden+1))/((reference_support+.5)/(refden+1))
    order=sorted(range(len(names)),key=lambda i:(-int(target_support[i]),-float(ratio[i]),-int(target_messages[i]),names[i]))[:limit]
    period_vectors={}
    for period in PERIODS:
        af=np.array([period_for(records[next(iter(owner.getrow(j).indices))]['alert_start_time'])==period for j in range(len(aids))]) & flags
        period_vectors[period]=np.asarray(alert_matrix[af].sum(axis=0)).ravel()
    monthly={}
    for month in sorted({r['alert_start_time'].astimezone(KYIV).strftime('%Y-%m') for r in records}):
        af=np.array([records[next(iter(owner.getrow(j).indices))]['alert_start_time'].astimezone(KYIV).strftime('%Y-%m')==month for j in range(len(aids))]) & flags
        monthly[month]=np.asarray(alert_matrix[af].sum(axis=0)).ravel()
    output=[]
    columns=matrix.tocsc()
    for i in order:
        hits=[j for j in columns.getcol(i).indices if msgflags[j]]
        sample=[];seen_alerts=set()
        for j in hits:
            if records[j]['alert_id'] in seen_alerts:continue
            sample.append(records[j]);seen_alerts.add(records[j]['alert_id'])
            if len(sample)==3:break
        output.append(dict(ngram=names[i],ngram_type=kind,unique_alert_support=int(target_support[i]),unique_message_support=int(target_messages[i]),
          specific_alert_support=int(reference_support[i]),specific_message_support=int(ref_messages[i]),
          target_alert_denominator=targetden,specific_alert_denominator=refden,
          target_alert_prevalence=float(target_support[i]/targetden) if targetden else None,
          specific_alert_prevalence=float(reference_support[i]/refden) if refden else None,
          smoothed_prevalence_ratio=float(ratio[i]),period_distribution={p:int(v[i]) for p,v in period_vectors.items()},
          monthly_distribution={m:int(v[i]) for m,v in monthly.items()},
          representative_alert_ids=[r['alert_id'] for r in sample],representative_message_ids=[r['message_id'] for r in sample],
          representative_texts=[r['text'] for r in sample],representative_timestamps=[r['message_time'] for r in sample]))
    distinctive={}
    for period,vector in period_vectors.items():
        in_period=sum(period_for(r['alert_start_time'])==period and r['population'] in POPULATIONS[1:3] for r in {r['alert_id']:r for r in records}.values())
        otherden=targetden-in_period
        rest=target_support-vector
        drift=((vector+.5)/(in_period+1))/((rest+.5)/(otherden+1))
        ranked=sorted([i for i in range(len(names)) if vector[i]>=3],key=lambda i:(-float(drift[i]),-int(vector[i]),names[i]))[:15]
        distinctive[period]=[dict(phrase=names[i],unique_alert_support=int(vector[i]),alert_text_denominator=in_period,smoothed_period_vs_rest_ratio=float(drift[i])) for i in ranked]
    return output,distinctive,dict(features=len(names),matrix_shape=list(matrix.shape),sparse_nnz=int(matrix.nnz),document_min_frequency=3)


def group_similar(records, seed=20261011, groups=64):
    """Sparse TF-IDF + weighted MiniBatchKMeans; centroid cosine only."""
    texts=[r['normalized_text'] for r in records]
    unique=sorted(set(t for t in texts if t))
    if not unique:return [],[],dict(groups=0)
    word=TfidfVectorizer(analyzer=word_ngrams,min_df=2,max_features=25000,sublinear_tf=True,dtype=np.float32)
    char=TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=2,max_features=35000,sublinear_tf=True,dtype=np.float32)
    # Tiny synthetic corpora can legitimately have no repeated n-gram.
    if len(unique)<3:word.set_params(min_df=1);char.set_params(min_df=1)
    def fit_with_fallback(vectorizer):
        try:return vectorizer.fit_transform(unique)
        except ValueError as exc:
            if 'no terms remain' not in str(exc) and 'empty vocabulary' not in str(exc):raise
            vectorizer.set_params(min_df=1)
            try:return vectorizer.fit_transform(unique)
            except ValueError as fallback:
                if 'empty vocabulary' not in str(fallback):raise
                # E.g. only function words: retain char representation.
                return sparse.csr_matrix((len(unique),0),dtype=np.float32)
    wx=fit_with_fallback(word);cx=fit_with_fallback(char)
    x=sparse_normalize(sparse.hstack([wx,cx],format='csr'))
    lookup={t:i for i,t in enumerate(unique)}
    counts=Counter(r['alert_id'] for r in records)
    weights=np.zeros(len(unique),dtype=np.float64)
    for r in records:
        if r['normalized_text']:weights[lookup[r['normalized_text']]]+=1/counts[r['alert_id']]
    k=min(groups,len(unique))
    # Single-thread math plus fixed seed/order guarantees reproducible grouping.
    with threadpool_limits(limits=1):
        model=MiniBatchKMeans(n_clusters=k,random_state=seed,n_init=3,batch_size=1024,max_iter=80,reassignment_ratio=0)
        model.fit(x,sample_weight=weights)
        labels=model.predict(x)
    centroids=sparse_normalize(model.cluster_centers_)
    # Only n_docs x one assigned centroid, in bounded chunks; no pairwise matrix.
    cos=np.empty(len(unique),dtype=np.float64)
    for start in range(0,len(unique),256):
        stop=min(start+256,len(unique))
        cos[start:stop]=np.asarray(x[start:stop].multiply(centroids[labels[start:stop]]).sum(axis=1)).ravel()
    names=np.concatenate([word.get_feature_names_out() if wx.shape[1] else np.array([]),char.get_feature_names_out() if cx.shape[1] else np.array([])])
    summaries=[];members=defaultdict(list);assign=[]
    for r in records:
        t=r['normalized_text']
        if not t:continue
        i=lookup[t];cluster=int(labels[i]);members[cluster].append(r)
        assign.append(dict(alert_id=r['alert_id'],message_id=r['message_id'],cluster_id=f'G{cluster:03d}',cosine_to_centroid=float(cos[i]),population=r['population']))
    for cluster,rows in sorted(members.items()):
        target=[r for r in rows if r['population'] in POPULATIONS[1:3]]
        support=len({r['alert_id'] for r in target})
        tops=np.argsort(-centroids[cluster,:wx.shape[1]])[:8]
        example_rows=sorted(target,key=lambda r:(-cos[lookup[r['normalized_text']]],r['message_time'],r['message_id']))
        examples=[];seen=set();seenalerts=set()
        for r in example_rows:
            if r['normalized_text'] in seen:continue
            if r['alert_id'] in seenalerts and len(seenalerts)<min(5,support):continue
            examples.append(r);seen.add(r['normalized_text']);seenalerts.add(r['alert_id'])
            if len(examples)==5:break
        summaries.append(dict(cluster_id=f'G{cluster:03d}',unique_alert_support=support,unique_message_support=len({r['message_id'] for r in target}),
          specific_alert_support=len({r['alert_id'] for r in rows if r['population']==POPULATIONS[0]}),
          top_word_ngrams=[names[i] for i in tops],mean_cosine=float(np.mean([cos[lookup[r['normalized_text']]] for r in target])) if target else None,
          representative_message_ids=[r['message_id'] for r in examples],representative_alert_ids=[r['alert_id'] for r in examples],representative_texts=[r['text'] for r in examples],
          human_decision='',review_notes=''))
    summaries.sort(key=lambda s:(-s['unique_alert_support'],-s['unique_message_support'],s['cluster_id']))
    return assign,summaries,dict(method='sparse word+char TF-IDF; alert-balanced MiniBatchKMeans; assigned-centroid cosine',seed=seed,groups=k,unique_normalized_documents=len(unique),matrix_shape=list(x.shape),sparse_nnz=int(x.nnz),word_features=wx.shape[1],character_features=cx.shape[1],max_pairwise_matrix='none',weights='each alert contributes total weight <=1',cosine_chunk_size=256,word_min_df=word.min_df,char_min_df=char.min_df)
